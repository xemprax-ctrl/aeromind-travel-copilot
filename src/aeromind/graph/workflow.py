from __future__ import annotations

import re
import uuid
from typing import Any

from langgraph.graph import END, StateGraph

from aeromind.agents.openrouter import extract_travel_constraints
from aeromind.config import Settings
from aeromind.models import TravelState
from aeromind.observability.logger import ObservabilityLogger
from aeromind.security.guardrails import SecurityGuardrails
from aeromind.tools.flights import DESTINATION_NAMES, MOCK_FLIGHTS, search_and_price
from aeromind.tools.research import research_travel_topic


DESTINATION_CODES = DESTINATION_NAMES
SUPPORTED_ROUTES = {
    (flight["origin"], flight["destination"])
    for flight in MOCK_FLIGHTS
}


def initial_state(
    user_query: str,
    origin: str | None = None,
    destination: str | None = None,
    budget: float | None = None,
    extra_bags: int | None = None,
    direct_only: bool | None = None,
    allow_stopovers: bool | None = None,
    require_stopover: bool | None = None,
) -> TravelState:
    return {
        "trace_id": str(uuid.uuid4()),
        "user_query": user_query,
        "sanitized_query": "",
        "origin": origin or "RUH",
        "destination": destination or "",
        "max_budget": budget if budget is not None else 3000.0,
        "departure_date": "",
        "extra_bags": extra_bags if extra_bags is not None else 0,
        "direct_only": direct_only if direct_only is not None else False,
        "allow_stopovers": allow_stopovers if allow_stopovers is not None else True,
        "require_stopover": require_stopover if require_stopover is not None else False,
        "research_context": [],
        "candidate_flights": [],
        "selected_plan": None,
        "critique_feedback": "",
        "is_approved": False,
        "revision_count": 0,
        "final_response": "",
        "error_message": "",
        "terminal_reason": "INVALID_INPUT",
    }


def security_node(state: TravelState, logger: ObservabilityLogger) -> TravelState:
    trace_id = state["trace_id"]
    finish = logger.timed(trace_id, "Security Agent", "validate_input_and_mask_pii")
    valid, message = SecurityGuardrails.validate_input(state["user_query"])
    if not valid:
        state["error_message"] = message
        state["terminal_reason"] = "SECURITY_BLOCKED"
        finish("BLOCKED", {"reason": message})
        return state

    state["sanitized_query"] = SecurityGuardrails.mask_pii(state["user_query"])
    pii_masked = state["sanitized_query"] != state["user_query"]
    # Keep the original input only long enough to validate it; downstream
    # nodes and logs operate on the PII-masked copy.
    state["user_query"] = state["sanitized_query"]
    finish("SUCCESS", {"pii_masked": pii_masked})
    return state


def planner_node(state: TravelState, logger: ObservabilityLogger, settings: Settings) -> TravelState:
    trace_id = state["trace_id"]
    finish = logger.timed(trace_id, "Planner Agent", "parse_travel_constraints")
    query = state["sanitized_query"]

    structured_destination = state.get("destination", "")
    if structured_destination:
        finish("SUCCESS", {
            "origin": state["origin"],
            "destination": state["destination"],
            "budget": state["max_budget"],
            "direct_only": state["direct_only"],
            "extra_bags": state["extra_bags"],
        })
        if state["origin"] == state["destination"]:
            state["error_message"] = "يجب أن تختلف نقطة الانطلاق عن الوجهة."
            state["terminal_reason"] = "INVALID_INPUT"
        elif (state["origin"], state["destination"]) not in SUPPORTED_ROUTES:
            state["error_message"] = "الوجهة أو نقطة الانطلاق غير مدعومة في قاعدة الرحلات المحاكاة."
            state["terminal_reason"] = "INVALID_INPUT"
        return state

    llm_result = extract_travel_constraints(query, settings)
    llm_data = llm_result.get("data") if llm_result.get("enabled") else None
    llm_data = llm_data if isinstance(llm_data, dict) else {}

    destination = ""
    lowered = query.lower()
    for keyword, code in DESTINATION_CODES.items():
        if keyword.lower() in lowered:
            destination = code
            break

    llm_destination = str(llm_data.get("destination") or "").strip()
    if llm_destination and llm_destination.lower() not in {"null", "none", "unknown", "غير معروف", "not specified"}:
        destination_hint = llm_destination.lower()
        destination = DESTINATION_CODES.get(destination_hint, llm_destination.upper())
        destination_aliases = {"LON": "LHR", "NYC": "JFK", "SGN": "SIN"}
        destination = destination_aliases.get(destination, destination)

    origin_match = re.search(r"(?:من|from)\s+(RUH|JED|DMM|MED)|\b(RUH|JED|DMM|MED)\b", query, re.IGNORECASE)
    origin = origin_match.group(1) or origin_match.group(2) if origin_match else "RUH"
    llm_origin = str(llm_data.get("origin") or "").strip().upper()
    if llm_origin in {"RUH", "JED", "DMM", "MED"}:
        origin = llm_origin

    budget_matches = re.findall(r"(?<!\d)(\d{3,6})(?:\s*(?:ريال|SAR|sar))", query)
    max_budget = float(budget_matches[0]) if budget_matches else 3000.0
    try:
        llm_budget = llm_data.get("budget_sar")
        if llm_budget is not None:
            max_budget = float(llm_budget)
    except (TypeError, ValueError):
        pass

    direct_only = bool(re.search(r"مباشر|بدون\s*توقف|non.?stop|direct", query, re.IGNORECASE))
    if "direct_only" in llm_data:
        direct_only = bool(llm_data.get("direct_only"))

    extra_bags = 1 if re.search(r"حقيبة|شنطة|baggage|luggage|bag", query, re.IGNORECASE) else 0
    try:
        llm_bags = llm_data.get("extra_bags")
        if llm_bags is not None:
            extra_bags = max(0, min(5, int(llm_bags)))
    except (TypeError, ValueError):
        pass

    if max_budget <= 0:
        state["error_message"] = "الميزانية يجب أن تكون قيمة موجبة."
        state["terminal_reason"] = "INVALID_INPUT"
        finish("ERROR", {"budget": max_budget})
        return state

    state.update({
        "origin": origin,
        "destination": destination,
        "max_budget": max_budget,
        "direct_only": direct_only,
        "extra_bags": extra_bags,
    })

    if not destination:
        state["error_message"] = "لم يتم تحديد وجهة سفر. اذكر اسم الوجهة أو رمز المطار، مثل دبي أو DXB."
        state["terminal_reason"] = "INVALID_INPUT"
        finish("ERROR", {"origin": origin, "destination": destination})
        return state

    if (origin, destination) not in SUPPORTED_ROUTES:
        state["error_message"] = "الوجهة أو نقطة الانطلاق غير مدعومة في قاعدة الرحلات المحاكاة."
        state["terminal_reason"] = "INVALID_INPUT"
        finish("ERROR", {"origin": origin, "destination": destination})
        return state

    finish("SUCCESS", {"origin": origin, "destination": destination, "budget": max_budget, "direct_only": direct_only})
    return state


def research_node(state: TravelState, logger: ObservabilityLogger, settings: Settings) -> TravelState:
    trace_id = state["trace_id"]
    finish = logger.timed(trace_id, "Travel Research Agent", "research_supporting_context")
    query = f"Travel requirements, baggage policy and current advisories for {state['origin']} to {state['destination']}"
    result = research_travel_topic(query, settings)
    state["research_context"] = result.get("results", [])[:5]
    if result.get("error"):
        state["critique_feedback"] = "تعذر جلب السياق الخارجي؛ استمر البحث ببيانات الرحلات المحاكاة."
        finish("ERROR", {"result_count": 0, "error": result["error"]})
    else:
        state["critique_feedback"] = "Tavily disabled or no supporting context was available." if not result.get("enabled") else "Supporting context retrieved."
        finish("SUCCESS" if result.get("enabled") else "SKIPPED", {"result_count": len(result.get("results", []))})
    return state


def worker_node(state: TravelState, logger: ObservabilityLogger, settings: Settings) -> TravelState:
    trace_id = state["trace_id"]
    finish = logger.timed(trace_id, "Flight Worker Agent", "search_and_price")

    allow_direct_only = state["direct_only"]
    if "تخفيف" in state.get("critique_feedback", ""):
        allow_direct_only = False

    try:
        options = search_and_price(
            state["origin"],
            state["destination"],
            state["extra_bags"],
            allow_direct_only,
            state.get("allow_stopovers", True),
            state.get("require_stopover", False),
        )
    except Exception as exc:
        state["candidate_flights"] = []
        state["selected_plan"] = None
        state["error_message"] = "فشل في تشغيل أداة البحث والتسعير."
        state["terminal_reason"] = "TOOL_FAILURE"
        finish("ERROR", {"error": type(exc).__name__})
        return state

    state["candidate_flights"] = options
    affordable = [option for option in options if option["total_price_sar"] <= state["max_budget"]]
    state["selected_plan"] = affordable[0] if affordable else None
    if options and not affordable:
        state["terminal_reason"] = "NO_RESULTS"
        state["critique_feedback"] = "توجد رحلات، لكن أرخص خيار يتجاوز الميزانية المحددة."
    finish("SUCCESS", {"candidate_count": len(options), "selected": state["selected_plan"]})
    return state


def reviewer_node(state: TravelState, logger: ObservabilityLogger, settings: Settings) -> TravelState:
    trace_id = state["trace_id"]
    finish = logger.timed(trace_id, "Reviewer Agent", "critique_plan")
    plan = state.get("selected_plan")

    if not plan:
        state["is_approved"] = False
        if state.get("terminal_reason") not in {"NO_RESULTS", "TOOL_FAILURE"}:
            state["terminal_reason"] = "NO_RESULTS"
            state["critique_feedback"] = "لم يتم العثور على رحلة تطابق القيود الحالية."
        finish(
            "ERROR" if state.get("terminal_reason") == "TOOL_FAILURE" else "REJECTED",
            {"reason": state.get("terminal_reason", "NO_RESULTS")},
        )
        return state

    valid_output, output_message = SecurityGuardrails.validate_output(plan, state["max_budget"])
    if not valid_output:
        state["is_approved"] = False
        state["revision_count"] = state.get("revision_count", 0) + 1
        state["critique_feedback"] = f"{output_message}. تقليل القيود غير المباشرة فقط عند السماح بذلك."
        state["terminal_reason"] = "REVISION_LIMIT" if state["revision_count"] >= settings.max_revisions else "INVALID_INPUT"
        finish("REJECTED", {"reason": output_message, "revision_count": state["revision_count"]})
        return state

    if state["direct_only"] and plan["stops"] != 0:
        state["is_approved"] = False
        state["revision_count"] = state.get("revision_count", 0) + 1
        state["critique_feedback"] = "تعارضت الرحلة مع شرط عدم التوقف. لا تخفف هذا الشرط دون موافقة صريحة من المستخدم."
        state["terminal_reason"] = "REVISION_LIMIT" if state["revision_count"] >= settings.max_revisions else "INVALID_INPUT"
        finish("REJECTED", {"reason": "DIRECT_ONLY_CONFLICT"})
        return state

    state["is_approved"] = True
    state["terminal_reason"] = "APPROVED"
    state["critique_feedback"] = "الخطة مطابقة للميزانية وجميع القيود."
    finish("APPROVED", {"selected_flight": plan["flight_id"]})
    return state


def finalizer_node(state: TravelState, logger: ObservabilityLogger) -> TravelState:
    trace_id = state["trace_id"]
    finish = logger.timed(trace_id, "Finalizer Agent", "format_safe_response")

    if state.get("terminal_reason") == "SECURITY_BLOCKED":
        state["final_response"] = state["error_message"]
    elif state.get("terminal_reason") == "INVALID_INPUT":
        state["final_response"] = state.get("error_message") or "البيانات المدخلة غير صالحة."
    elif state.get("terminal_reason") == "NO_RESULTS":
        state["final_response"] = state.get("critique_feedback") or "تعذر العثور على رحلة مطابقة للقيود المحددة."
    elif state.get("terminal_reason") == "TOOL_FAILURE":
        state["final_response"] = state.get("error_message") or "فشلت أداة الرحلات."
    elif state.get("terminal_reason") == "REVISION_LIMIT":
        state["final_response"] = "تعذر اعتماد خطة آمنة بعد الحد المسموح من التصحيحات. " + state.get("critique_feedback", "")
    elif state.get("is_approved") and state.get("selected_plan"):
        plan = state["selected_plan"]
        state["final_response"] = (
            "تم اعتماد الخطة:\n"
            f"- شركة الطيران: {plan['airline']} ({plan['flight_id']})\n"
            f"- المسار: {plan['origin']} -> {plan['destination']} | التوقفات: {plan['stops']} | المدة: {plan['duration']}\n"
            f"- التكلفة: {plan['total_price_sar']} SAR، ضمن الميزانية: {state['max_budget']} SAR"
        )
    else:
        state["final_response"] = "تعذر اعتماد خطة سفر مناسبة ضمن القيود الحالية."

    finish("SUCCESS", {"terminal_reason": state["terminal_reason"]})
    return state


def route_after_security(state: TravelState) -> str:
    return "finalizer" if state.get("terminal_reason") == "SECURITY_BLOCKED" else "planner"


def route_after_planner(state: TravelState) -> str:
    return "finalizer" if state.get("error_message") else "research"


def route_after_research(state: TravelState) -> str:
    return "worker"


def route_after_reviewer(state: TravelState, max_revisions: int = 2) -> str:
    if state.get("is_approved"):
        return "finalizer"
    if state.get("revision_count", 0) >= max_revisions:
        state["terminal_reason"] = "REVISION_LIMIT"
        return "finalizer"
    if state.get("terminal_reason") in {"NO_RESULTS", "TOOL_FAILURE"}:
        return "finalizer"
    return "worker"


class AeroMindWorkflow:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings.from_env()
        self.logger = ObservabilityLogger()
        self.app = self._build()

    def _build(self):
        graph = StateGraph(TravelState)
        graph.add_node("security", lambda state: security_node(state, self.logger))
        graph.add_node("planner", lambda state: planner_node(state, self.logger, self.settings))
        graph.add_node("research", lambda state: research_node(state, self.logger, self.settings))
        graph.add_node("worker", lambda state: worker_node(state, self.logger, self.settings))
        graph.add_node("reviewer", lambda state: reviewer_node(state, self.logger, self.settings))
        graph.add_node("finalizer", lambda state: finalizer_node(state, self.logger))

        graph.set_entry_point("security")
        graph.add_conditional_edges("security", route_after_security)
        graph.add_conditional_edges("planner", route_after_planner)
        graph.add_conditional_edges("research", route_after_research)
        graph.add_edge("worker", "reviewer")
        graph.add_conditional_edges("reviewer", lambda state: route_after_reviewer(state, self.settings.max_revisions))
        graph.add_edge("finalizer", END)
        return graph.compile()

    def run(
        self,
        query: str,
        origin: str | None = None,
        destination: str | None = None,
        budget: float | None = None,
        extra_bags: int | None = None,
        direct_only: bool | None = None,
        allow_stopovers: bool | None = None,
        require_stopover: bool | None = None,
    ) -> TravelState:
        return self.app.invoke(initial_state(
            query,
            origin=origin,
            destination=destination,
            budget=budget,
            extra_bags=extra_bags,
            direct_only=direct_only,
            allow_stopovers=allow_stopovers,
            require_stopover=require_stopover,
        ))

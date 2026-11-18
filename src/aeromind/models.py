from __future__ import annotations

from datetime import date
from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field, field_validator


class TravelRequest(BaseModel):
    query: str = Field(min_length=3, max_length=500)
    origin: str | None = Field(default=None, min_length=3, max_length=20)
    destination: str | None = Field(default=None, min_length=3, max_length=20)
    budget_sar: float | None = Field(default=None, gt=0)
    departure_date: date | None = None
    extra_bags: int = Field(default=0, ge=0, le=5)
    direct_only: bool = False


class FlightOption(BaseModel):
    flight_id: str
    airline: str
    origin: str
    destination: str
    base_price_sar: float
    tax_sar: float
    baggage_fee_sar: float
    total_price_sar: float
    stops: int = Field(ge=0)
    stopover_airport: str | None = None
    duration: str


class TravelPlan(BaseModel):
    trace_id: str
    request: TravelRequest
    candidates: list[FlightOption] = Field(default_factory=list)
    selected: FlightOption | None = None
    critique: str = ""
    approved: bool = False
    final_response: str = ""


class TravelState(TypedDict, total=False):
    trace_id: str
    user_query: str
    sanitized_query: str
    origin: str
    destination: str
    max_budget: float
    departure_date: str
    extra_bags: int
    direct_only: bool
    allow_stopovers: bool
    require_stopover: bool
    research_context: list[dict[str, Any]]
    candidate_flights: list[dict[str, Any]]
    selected_plan: dict[str, Any] | None
    critique_feedback: str
    is_approved: bool
    revision_count: int
    final_response: str
    error_message: str
    terminal_reason: Literal[
        "APPROVED",
        "SECURITY_BLOCKED",
        "INVALID_INPUT",
        "NO_RESULTS",
        "REVISION_LIMIT",
        "TOOL_FAILURE",
    ]

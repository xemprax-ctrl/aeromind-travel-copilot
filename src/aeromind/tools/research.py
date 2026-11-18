from __future__ import annotations

from typing import Any

from aeromind.config import Settings


def research_travel_topic(query: str, settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or Settings.from_env()
    if not settings.tavily_enabled:
        return {
            "enabled": False,
            "results": [],
            "note": "Tavily is not configured; mock and policy-safe fallback is active.",
        }

    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=settings.tavily_api_key)
        response = client.search(query=query, search_depth="basic", max_results=5)
        return {
            "enabled": True,
            "results": response.get("results", []),
            "query": query,
        }
    except Exception as exc:
        return {
            "enabled": True,
            "results": [],
            "error": type(exc).__name__,
        }

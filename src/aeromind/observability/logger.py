from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any


class ObservabilityLogger:
    def __init__(self) -> None:
        self.logs: list[dict[str, Any]] = []

    def new_trace_id(self) -> str:
        return str(uuid.uuid4())

    def log_event(
        self,
        trace_id: str,
        agent_name: str,
        action: str,
        status: str = "SUCCESS",
        details: Any = None,
        duration_ms: float = 0.0,
    ) -> dict[str, Any]:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trace_id": trace_id,
            "agent": agent_name,
            "action": action,
            "status": status,
            "duration_ms": round(duration_ms, 2),
            "details": details,
        }
        self.logs.append(entry)
        return entry

    def export(self) -> str:
        return json.dumps(self.logs, ensure_ascii=False, indent=2)

    def timed(self, trace_id: str, agent_name: str, action: str):
        start = time.perf_counter()

        def finish(status: str = "SUCCESS", details: Any = None) -> None:
            duration_ms = (time.perf_counter() - start) * 1000
            self.log_event(trace_id, agent_name, action, status, details, duration_ms)

        return finish

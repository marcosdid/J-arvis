from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class WsEvent:
    type: str
    session_id: str
    payload: dict[str, Any]
    at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "session_id": self.session_id,
            "payload": self.payload,
            "at": self.at,
        }

    @classmethod
    def session_status(
        cls, *, session_id: str, new_status: str, previous_status: str
    ) -> "WsEvent":
        return cls(
            type="session.status",
            session_id=session_id,
            payload={"status": new_status, "previous": previous_status},
        )

    @classmethod
    def session_tool_use(cls, *, session_id: str, tool: str) -> "WsEvent":
        return cls(
            type="session.tool_use",
            session_id=session_id,
            payload={"tool": tool},
        )

    @classmethod
    def session_stopped(cls, *, session_id: str) -> "WsEvent":
        return cls(type="session.stopped", session_id=session_id, payload={})

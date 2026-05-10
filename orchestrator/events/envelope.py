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
    task_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "session_id": self.session_id,
            "task_id": self.task_id,
            "payload": self.payload,
            "at": self.at,
        }

    @classmethod
    def session_status(
        cls,
        *,
        session_id: str,
        task_id: str,
        new_status: str,
        previous_status: str,
    ) -> "WsEvent":
        return cls(
            type="session.status",
            session_id=session_id,
            task_id=task_id,
            payload={"status": str(new_status), "previous": str(previous_status)},
        )

    @classmethod
    def session_tool_use(cls, *, session_id: str, task_id: str, tool: str) -> "WsEvent":
        return cls(
            type="session.tool_use",
            session_id=session_id,
            task_id=task_id,
            payload={"tool": tool},
        )

    @classmethod
    def session_stopped(cls, *, session_id: str, task_id: str) -> "WsEvent":
        return cls(type="session.stopped", session_id=session_id, task_id=task_id, payload={})

    @classmethod
    def task_created(
        cls,
        *,
        task_id: str,
        project_id: str,
        title: str,
        state: str,
    ) -> "WsEvent":
        return cls(
            type="task.created",
            session_id="",
            task_id=task_id,
            payload={"project_id": project_id, "title": title, "state": state},
        )

    @classmethod
    def task_updated(
        cls,
        *,
        task_id: str,
        project_id: str,
        title: str,
        new_state: str,
        previous_state: str | None,
    ) -> "WsEvent":
        return cls(
            type="task.updated",
            session_id="",
            task_id=task_id,
            payload={
                "project_id": project_id,
                "title": title,
                "state": new_state,
                "previous_state": previous_state,
            },
        )

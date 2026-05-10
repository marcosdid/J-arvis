from datetime import datetime

from orchestrator.events.envelope import WsEvent


def test_session_status_event_serialisation() -> None:
    event = WsEvent.session_status(
        session_id="sess-1",
        task_id="task-1",
        new_status="awaiting_response",
        previous_status="executing",
    )
    serialised = event.to_dict()
    assert serialised["type"] == "session.status"
    assert serialised["session_id"] == "sess-1"
    assert serialised["task_id"] == "task-1"
    assert serialised["payload"] == {
        "status": "awaiting_response",
        "previous": "executing",
    }
    datetime.fromisoformat(serialised["at"])


def test_session_tool_use_event() -> None:
    event = WsEvent.session_tool_use(session_id="sess-1", task_id="task-1", tool="Bash")
    serialised = event.to_dict()
    assert serialised["type"] == "session.tool_use"
    assert serialised["payload"] == {"tool": "Bash"}


def test_session_stopped_event_payload_empty() -> None:
    event = WsEvent.session_stopped(session_id="sess-1", task_id="task-1")
    assert event.to_dict()["type"] == "session.stopped"
    assert event.to_dict()["payload"] == {}


def test_at_is_timezone_aware() -> None:
    event = WsEvent.session_stopped(session_id="x", task_id="t1")
    parsed = datetime.fromisoformat(event.to_dict()["at"])
    assert parsed.tzinfo is not None

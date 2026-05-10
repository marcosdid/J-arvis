from orchestrator.events.envelope import WsEvent


def test_task_created_factory() -> None:
    e = WsEvent.task_created(
        task_id="t1", project_id="p1", title="X", state="idea"
    )
    d = e.to_dict()
    assert d["type"] == "task.created"
    assert d["task_id"] == "t1"
    assert d["session_id"] == ""
    assert d["payload"] == {
        "project_id": "p1", "title": "X", "state": "idea",
    }


def test_task_updated_factory() -> None:
    e = WsEvent.task_updated(
        task_id="t1", project_id="p1", title="X",
        new_state="ready", previous_state="idea",
    )
    d = e.to_dict()
    assert d["type"] == "task.updated"
    assert d["task_id"] == "t1"
    assert d["payload"]["state"] == "ready"
    assert d["payload"]["previous_state"] == "idea"


def test_session_status_factory_carries_task_id() -> None:
    from orchestrator.core.sessions import SessionStatus
    e = WsEvent.session_status(
        session_id="s1", task_id="t1",
        new_status=SessionStatus.IDLE, previous_status=SessionStatus.EXECUTING,
    )
    d = e.to_dict()
    assert d["session_id"] == "s1"
    assert d["task_id"] == "t1"


def test_session_tool_use_factory_carries_task_id() -> None:
    e = WsEvent.session_tool_use(session_id="s1", task_id="t1", tool="Bash")
    assert e.to_dict()["task_id"] == "t1"


def test_session_stopped_factory_carries_task_id() -> None:
    e = WsEvent.session_stopped(session_id="s1", task_id="t1")
    assert e.to_dict()["task_id"] == "t1"

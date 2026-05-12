"""F8.c: dispatch routing do call_tool com state injection via contextvar."""
import json
from typing import Any

import pytest

from orchestrator.core.catalog import Catalog, PermissionProfileSpec
from orchestrator.mcp.server import (
    McpDeps,
    _broadcast_task_created,
    _broadcast_task_updated,
    _create_task_tool,
    call_tool,
    list_tools,
    reset_deps,
    set_deps,
)


async def test_list_tools_returns_read_and_write_tools() -> None:
    tools = await list_tools()
    names = [t.name for t in tools]
    assert set(names) == {
        # F8.c read-only
        "list_projects", "get_project", "list_tasks", "get_task",
        # F8.d write tools
        "create_task", "update_task", "discard_task",
    }


class _FakeSession:
    """Minimal AsyncSession stub. Tools never call it for the unknown-tool path."""

    async def execute(self, _stmt: Any) -> Any:  # pragma: no cover
        raise AssertionError("unknown-tool path should not hit DB")


class _FakeSessionCm:
    async def __aenter__(self) -> _FakeSession:
        return _FakeSession()

    async def __aexit__(self, *_: Any) -> None:
        return None


class _FakeDb:
    def session(self) -> _FakeSessionCm:
        return _FakeSessionCm()


async def test_call_tool_unknown_raises() -> None:
    deps = McpDeps(db=_FakeDb(), catalog=None, broadcaster=None, git_ops=None)
    token = set_deps(deps)
    try:
        with pytest.raises(ValueError, match="unknown tool"):
            await call_tool("definitely_not_a_tool", {})
    finally:
        reset_deps(token)


class _RecordingSession:
    """AsyncSession stub that lets tools `get`/`execute` against fake rows."""

    def __init__(
        self,
        rows: list[Any] | None = None,
        single: Any | None = None,
    ) -> None:
        self._rows = rows or []
        self._single = single

    async def get(self, _model: Any, _pk: str) -> Any:
        return self._single

    async def execute(self, _stmt: Any) -> Any:
        class _Result:
            def __init__(self, rows: list[Any]) -> None:
                self._rows = rows

            def scalars(self) -> "_Result":
                return self

            def all(self) -> list[Any]:
                return self._rows

        return _Result(self._rows)


class _FakeRow:
    """Tuple-like stand-in for Project/Task rows. Attrs match _serialize_*."""

    def __init__(self, **kw: Any) -> None:
        for k, v in kw.items():
            setattr(self, k, v)


class _ScriptedDb:
    """`db.session()` returns the next pre-recorded session in `_queue`."""

    def __init__(self, sessions: list[_RecordingSession]) -> None:
        self._queue = list(sessions)

    def session(self) -> "_ScriptedDb._Cm":
        return self._Cm(self._queue.pop(0))

    class _Cm:
        def __init__(self, sess: _RecordingSession) -> None:
            self._sess = sess

        async def __aenter__(self) -> _RecordingSession:
            return self._sess

        async def __aexit__(self, *_: Any) -> None:
            return None


async def test_call_tool_list_projects_serializes_rows() -> None:
    row = _FakeRow(id="p1", name="proj", path="/tmp/p")
    db = _ScriptedDb([_RecordingSession(rows=[row])])
    token = set_deps(McpDeps(db=db, catalog=None, broadcaster=None, git_ops=None))
    try:
        out = await call_tool("list_projects", {})
    finally:
        reset_deps(token)
    assert len(out) == 1
    payload = json.loads(out[0].text)
    assert payload == [{"id": "p1", "name": "proj", "path": "/tmp/p"}]


async def test_call_tool_get_project_returns_single() -> None:
    row = _FakeRow(id="p2", name="other", path="/tmp/o")
    db = _ScriptedDb([_RecordingSession(single=row)])
    token = set_deps(McpDeps(db=db, catalog=None, broadcaster=None, git_ops=None))
    try:
        out = await call_tool("get_project", {"project_id": "p2"})
    finally:
        reset_deps(token)
    payload = json.loads(out[0].text)
    assert payload == {"id": "p2", "name": "other", "path": "/tmp/o"}


async def test_call_tool_list_tasks_no_filter_returns_all() -> None:
    rows = [
        _FakeRow(
            id="t1", project_id="p1", title="a", description=None, state="idea",
            branch=None, template=None, permission_profile=None,
        ),
        _FakeRow(
            id="t2", project_id="p1", title="b", description=None, state="done",
            branch=None, template=None, permission_profile=None,
        ),
    ]
    db = _ScriptedDb([_RecordingSession(rows=rows)])
    token = set_deps(McpDeps(db=db, catalog=None, broadcaster=None, git_ops=None))
    try:
        out = await call_tool("list_tasks", {})
    finally:
        reset_deps(token)
    payload = json.loads(out[0].text)
    assert [t["id"] for t in payload] == ["t1", "t2"]


async def test_call_tool_list_tasks_filters_by_state() -> None:
    # SQL push-down: core.list_tasks applies WHERE state=?, so the fake session
    # only returns rows matching the filter (mock at the SQL boundary).
    rows = [
        _FakeRow(
            id="t2", project_id="p1", title="b", description=None, state="done",
            branch=None, template=None, permission_profile=None,
        ),
    ]
    db = _ScriptedDb([_RecordingSession(rows=rows)])
    token = set_deps(McpDeps(db=db, catalog=None, broadcaster=None, git_ops=None))
    try:
        out = await call_tool(
            "list_tasks", {"project_id": "p1", "state": "done"},
        )
    finally:
        reset_deps(token)
    payload = json.loads(out[0].text)
    assert [t["id"] for t in payload] == ["t2"]


async def test_call_tool_get_task_returns_single() -> None:
    row = _FakeRow(
        id="t9", project_id="p1", title="x", description="d", state="ready",
        branch="feat/x", template=None, permission_profile="dev",
    )
    db = _ScriptedDb([_RecordingSession(single=row)])
    token = set_deps(McpDeps(db=db, catalog=None, broadcaster=None, git_ops=None))
    try:
        out = await call_tool("get_task", {"task_id": "t9"})
    finally:
        reset_deps(token)
    payload = json.loads(out[0].text)
    assert payload["id"] == "t9"
    assert payload["branch"] == "feat/x"
    assert payload["permission_profile"] == "dev"


# --- F8.d: write tools coverage ---------------------------------------------


class _RecordingBroadcaster:
    """In-memory WsBroadcaster stub. Captures published events."""

    def __init__(self) -> None:
        self.events: list[Any] = []

    async def publish(self, event: Any) -> None:
        self.events.append(event)


async def test_broadcast_task_created_publishes_event() -> None:
    b = _RecordingBroadcaster()
    task = _FakeRow(id="t1", project_id="p1", title="x", state="idea")
    await _broadcast_task_created(b, task)
    assert len(b.events) == 1
    assert b.events[0].type == "task.created"
    assert b.events[0].task_id == "t1"


async def test_broadcast_task_updated_publishes_event() -> None:
    b = _RecordingBroadcaster()
    task = _FakeRow(id="t1", project_id="p1", title="x", state="ready")
    await _broadcast_task_updated(b, task, previous_state="idea")
    assert len(b.events) == 1
    assert b.events[0].type == "task.updated"
    assert b.events[0].payload["previous_state"] == "idea"


async def test_broadcast_task_updated_preserves_none_prev_state() -> None:
    # Quando core.update_task retorna previous_state=None (no-op transition,
    # e.g. discard_task em task já `discarded`), o broadcast preserva None
    # ao invés de mascarar com task.state. Envelope contract aceita None;
    # passar new_state como fallback simularia uma falsa transição para
    # subscribers do Kanban.
    b = _RecordingBroadcaster()
    task = _FakeRow(id="t1", project_id="p1", title="x", state="discarded")
    await _broadcast_task_updated(b, task, previous_state=None)
    assert b.events[0].payload["previous_state"] is None


async def test_create_task_tool_requires_catalog() -> None:
    deps = McpDeps(db=_FakeDb(), catalog=None, broadcaster=None, git_ops=None)
    with pytest.raises(ValueError, match="catalog not configured"):
        await _create_task_tool(
            deps.db, deps.catalog, deps.broadcaster,
            {"project_id": "p1", "title": "t"},
        )


async def test_create_task_tool_translates_invalid_template_error() -> None:
    # Mock catalog com `templates` vazio → core.create_task levanta
    # InvalidTemplateError. _create_task_tool re-empacota como ValueError
    # com mensagem que vira erro JSON-RPC pelo SDK MCP.
    catalog = Catalog(
        version="1",
        fallback_permission_profile="default",
        permission_profiles={
            "default": PermissionProfileSpec(
                description="default", claude_args=[],
            ),
        },
        templates={},
    )
    db = _ScriptedDb([_RecordingSession()])
    with pytest.raises(ValueError, match="template_not_in_catalog"):
        await _create_task_tool(
            db, catalog, None,
            {"project_id": "p1", "title": "t", "template": "ghost"},
        )

"""F8.c: dispatch routing do call_tool com state injection via contextvar."""
import json
from typing import Any

import pytest

from orchestrator.mcp.server import (
    McpDeps,
    call_tool,
    list_tools,
    reset_deps,
    set_deps,
)


async def test_list_tools_returns_4_read_only_tools() -> None:
    tools = await list_tools()
    names = [t.name for t in tools]
    assert set(names) == {"list_projects", "get_project", "list_tasks", "get_task"}


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

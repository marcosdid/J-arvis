"""F7.d: sessions consomem permission_profile via catalog no spawn."""
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from sqlalchemy import update

from orchestrator.core.catalog import load_catalog
from orchestrator.main import create_app
from orchestrator.sandbox.aijail import AiJailRuntime
from orchestrator.store.database import Database
from orchestrator.store.models import Task
from tests.integration.conftest import _make_repo


class _CapturingProcessOps:
    """Captura argv sem spawnar processo de verdade."""
    def __init__(self) -> None:
        self.spawns: list[tuple[list[str], str]] = []

    def spawn(self, cmd: list[str], cwd: str) -> int:
        self.spawns.append((cmd, cwd))
        return 9999

    def kill(self, pid: int) -> None: pass


def _read_jail_command(cwd: Path) -> str:
    return (cwd / ".ai-jail").read_text().splitlines()[0]


async def test_session_with_default_profile_writes_empty_claude_args(
    db: Database, tmp_path: Path,
) -> None:
    """Template refactor → permission_profile=default → claude_args=[]."""
    ops = _CapturingProcessOps()
    runtime = AiJailRuntime(lambda: "xterm", ops)
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        proj = (await c.post("/api/projects", json={"name": "p", "path": str(repo)})).json()
        task = (await c.post("/api/tasks", json={
            "project_id": proj["id"], "title": "Explore", "template": "refactor",
        })).json()
        await c.patch(f"/api/tasks/{task['id']}", json={"state": "ready"})
        await c.post(f"/api/tasks/{task['id']}/sessions", json={})

    spawned_cwd = Path(ops.spawns[0][1])
    line = _read_jail_command(spawned_cwd)
    assert line == 'command = ["claude"]'


async def test_session_with_read_only_profile_writes_plan_mode(
    db: Database, tmp_path: Path,
) -> None:
    """Cobre o perfil `read-only` explicitamente (spec §9 requer).

    Nenhum template aponta pra read-only no catálogo atual; testamos via
    SQL direto pra setar permission_profile='read-only' na task."""
    ops = _CapturingProcessOps()
    runtime = AiJailRuntime(lambda: "xterm", ops)
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        proj = (await c.post("/api/projects", json={"name": "p", "path": str(repo)})).json()
        task = (await c.post("/api/tasks", json={
            "project_id": proj["id"], "title": "Review pr",
        })).json()
        async with db.session() as s:
            await s.execute(
                update(Task)
                .where(Task.id == task["id"])
                .values(permission_profile="read-only")
            )
            await s.commit()
        await c.patch(f"/api/tasks/{task['id']}", json={"state": "ready"})
        await c.post(f"/api/tasks/{task['id']}/sessions", json={})

    spawned_cwd = Path(ops.spawns[0][1])
    line = _read_jail_command(spawned_cwd)
    assert '"--permission-mode", "plan"' in line
    assert '"--allowed-tools", "Read,Grep,Glob,LS"' in line


async def test_session_back_compat_null_profile_uses_yolo_fallback(
    db: Database, tmp_path: Path,
) -> None:
    """Task sem template (template=NULL, permission_profile=NULL) →
    fallback do catalog = yolo = --dangerously-skip-permissions.
    Idêntico ao comportamento F1-F6."""
    ops = _CapturingProcessOps()
    runtime = AiJailRuntime(lambda: "xterm", ops)
    repo = _make_repo(tmp_path)
    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        proj = (await c.post("/api/projects", json={"name": "p", "path": str(repo)})).json()
        task = (await c.post("/api/tasks", json={
            "project_id": proj["id"], "title": "Old style",
        })).json()
        await c.patch(f"/api/tasks/{task['id']}", json={"state": "ready"})
        await c.post(f"/api/tasks/{task['id']}/sessions", json={})

    spawned_cwd = Path(ops.spawns[0][1])
    line = _read_jail_command(spawned_cwd)
    assert '"--dangerously-skip-permissions"' in line


async def test_session_stale_profile_returns_422(
    db: Database, tmp_path: Path,
) -> None:
    """Task com permission_profile='X' onde X foi removido do catálogo
    em runtime — start_session → 422."""
    ops = _CapturingProcessOps()
    runtime = AiJailRuntime(lambda: "xterm", ops)
    repo = _make_repo(tmp_path)

    minimal_catalog_yaml = """
version: "1"
fallback_permission_profile: default
permission_profiles:
  default: {description: "D", claude_args: []}
templates: {}
"""
    cat_path = tmp_path / "stale-catalog.yml"
    cat_path.write_text(minimal_catalog_yaml)
    stale_catalog = load_catalog(cat_path)

    app = create_app(database=db, runtime=runtime, ui_dist=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        proj = (await c.post("/api/projects", json={"name": "p", "path": str(repo)})).json()
        task = (await c.post("/api/tasks", json={
            "project_id": proj["id"], "title": "Fix", "template": "bugfix",
        })).json()
        await c.patch(f"/api/tasks/{task['id']}", json={"state": "ready"})

        app.state.catalog = stale_catalog

        r = await c.post(f"/api/tasks/{task['id']}/sessions", json={})

    assert r.status_code == 422
    body = r.json()
    assert body["detail"]["error"] == "permission_profile_not_in_catalog"
    assert body["detail"]["profile"] == "yolo"

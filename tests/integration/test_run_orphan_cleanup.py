"""F6.f: cleanup_orphan_runs_at_startup + derive_run_cwd com worktrees."""
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest

from orchestrator.core.port_allocator import PortAllocator
from orchestrator.core.runs import cleanup_orphan_runs_at_startup, derive_run_cwd
from orchestrator.sandbox.docker_ops import ContainerSpec, DockerError
from orchestrator.store.database import Database
from orchestrator.store.models import (
    Project,
    Repository,
    RunInstance,
    Task,
    Worktree,
)


class _FakeDocker:
    def __init__(self) -> None:
        self.stop_calls: list[tuple[str, bool]] = []
        self.rm_calls: list[str] = []
        self.network_rm_calls: list[str] = []
        self.fail_all = False

    async def build(self, *_a: Any, **_kw: Any) -> None:  # pragma: no cover
        pass

    async def network_create(self, _name: str) -> None:  # pragma: no cover
        pass

    async def network_rm(self, name: str) -> None:
        self.network_rm_calls.append(name)
        if self.fail_all:
            raise DockerError("network_rm failed", stderr="x")

    async def container_start(self, _spec: ContainerSpec) -> str:  # pragma: no cover
        return ""

    async def run_in_container(
        self, _cid: str, _cmd: list[str],
    ) -> tuple[int, str, str]:  # pragma: no cover
        return (0, "", "")

    def stream_logs(
        self, _container_id: str,
    ) -> AsyncIterator[tuple[str, str]]:  # pragma: no cover
        async def _empty() -> AsyncIterator[tuple[str, str]]:
            if False:
                yield "", ""
        return _empty()

    async def stop(self, cid: str, *, force: bool = False) -> None:
        self.stop_calls.append((cid, force))
        if self.fail_all:
            raise DockerError("stop failed", stderr="x")

    async def rm(self, cid: str) -> None:
        self.rm_calls.append(cid)
        if self.fail_all:
            raise DockerError("rm failed", stderr="x")


class _MockSock:
    def setsockopt(self, *_a: Any, **_kw: Any) -> None: pass
    def bind(self, *_a: Any, **_kw: Any) -> None: pass
    def close(self) -> None: pass


@pytest.mark.integration
async def test_cleanup_orphan_runs_marks_unfinished_as_stopped(
    tmp_path: Path,
) -> None:
    """Restart cenário: RunInstance com ended_at IS NULL → stop+rm
    containers, network_rm, release ports, marca stopped + error_message."""
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 't.db'}")
    await db.bootstrap()
    docker = _FakeDocker()
    alloc = PortAllocator(socket_factory=_MockSock)
    try:
        async with db.session() as s:
            project = Project(name="p", path=str(tmp_path / "p"))
            s.add(project)
            await s.commit()
            await s.refresh(project)
            task = Task(
                project_id=project.id, title="t", description="",
                state="in_progress",
            )
            s.add(task)
            await s.commit()
            await s.refresh(task)
            run = RunInstance(
                task_id=task.id, cwd="/x", manifest_path="/m",
                network_name="jarvis-run-abc",
                ports_json='{"db": 31100, "backend": 31101}',
                containers_json='{"db": "cid1", "backend": "cid2"}',
                status="ready",
            )
            s.add(run)
            await s.commit()
            run_id = run.id

        async with db.session() as s:
            await cleanup_orphan_runs_at_startup(s, docker, alloc)

        # Containers stopped + removed
        assert ("cid1", True) in docker.stop_calls
        assert ("cid2", True) in docker.stop_calls
        assert "cid1" in docker.rm_calls
        assert "cid2" in docker.rm_calls
        # Network removed
        assert docker.network_rm_calls == ["jarvis-run-abc"]
        # Run marcada stopped
        async with db.session() as s:
            row = await s.get(RunInstance, run_id)
            assert row.status == "stopped"
            assert row.ended_at is not None
            assert "orphaned" in (row.error_message or "")
    finally:
        await db.close()


@pytest.mark.integration
async def test_cleanup_orphan_runs_tolerates_docker_errors(tmp_path: Path) -> None:
    """Docker já desligou: stop/rm/network_rm raise — cleanup ignora e
    marca stopped mesmo assim."""
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 't.db'}")
    await db.bootstrap()
    docker = _FakeDocker()
    docker.fail_all = True
    alloc = PortAllocator(socket_factory=_MockSock)
    try:
        async with db.session() as s:
            project = Project(name="p", path=str(tmp_path / "p"))
            s.add(project)
            await s.commit()
            await s.refresh(project)
            task = Task(
                project_id=project.id, title="t", description="",
                state="in_progress",
            )
            s.add(task)
            await s.commit()
            await s.refresh(task)
            run = RunInstance(
                task_id=task.id, cwd="/x", manifest_path="/m",
                network_name="net",
                containers_json='{"a": "cid1"}',
                status="ready",
            )
            s.add(run)
            await s.commit()
            run_id = run.id

        async with db.session() as s:
            await cleanup_orphan_runs_at_startup(s, docker, alloc)

        async with db.session() as s:
            row = await s.get(RunInstance, run_id)
            assert row.status == "stopped"
    finally:
        await db.close()


@pytest.mark.integration
async def test_cleanup_skips_already_finished_runs(tmp_path: Path) -> None:
    """Run com ended_at != NULL não é re-processada."""
    from datetime import UTC, datetime

    db = Database(f"sqlite+aiosqlite:///{tmp_path / 't.db'}")
    await db.bootstrap()
    docker = _FakeDocker()
    alloc = PortAllocator(socket_factory=_MockSock)
    try:
        async with db.session() as s:
            project = Project(name="p", path=str(tmp_path / "p"))
            s.add(project)
            await s.commit()
            await s.refresh(project)
            task = Task(
                project_id=project.id, title="t", description="",
                state="in_progress",
            )
            s.add(task)
            await s.commit()
            await s.refresh(task)
            run = RunInstance(
                task_id=task.id, cwd="/x", manifest_path="/m",
                network_name="net",
                containers_json='{"a": "cid1"}',
                status="stopped",
                ended_at=datetime.now(UTC),
            )
            s.add(run)
            await s.commit()

        async with db.session() as s:
            await cleanup_orphan_runs_at_startup(s, docker, alloc)

        # Nenhuma chamada — run já terminada
        assert docker.stop_calls == []
        assert docker.network_rm_calls == []
    finally:
        await db.close()


@pytest.mark.integration
async def test_derive_run_cwd_with_monorepo_worktree(tmp_path: Path) -> None:
    """Task com 1 worktree (monorepo) → cwd = path do worktree."""
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 't.db'}")
    await db.bootstrap()
    try:
        async with db.session() as s:
            project = Project(name="p", path=str(tmp_path / "p"))
            s.add(project)
            await s.commit()
            await s.refresh(project)
            repo = Repository(
                project_id=project.id, name="p", sub_path=".",
            )
            s.add(repo)
            await s.commit()
            await s.refresh(repo)
            task = Task(
                project_id=project.id, title="t", description="",
                state="in_progress",
            )
            s.add(task)
            await s.commit()
            await s.refresh(task)
            wt = Worktree(
                repository_id=repo.id, task_id=task.id,
                path=str(tmp_path / "p--feature"),
                branch="feature",
            )
            s.add(wt)
            await s.commit()
            cwd = await derive_run_cwd(s, task)
            assert cwd == tmp_path / "p--feature"
    finally:
        await db.close()


@pytest.mark.integration
async def test_derive_run_cwd_with_multi_repo_worktrees(tmp_path: Path) -> None:
    """Task com 2 worktrees (multi-repo) → cwd = parent comum dos worktrees."""
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 't.db'}")
    await db.bootstrap()
    try:
        async with db.session() as s:
            project = Project(name="multi", path=str(tmp_path / "multi"))
            s.add(project)
            await s.commit()
            await s.refresh(project)
            r_back = Repository(
                project_id=project.id, name="backend", sub_path="backend",
            )
            r_front = Repository(
                project_id=project.id, name="frontend", sub_path="frontend",
            )
            s.add(r_back)
            s.add(r_front)
            await s.commit()
            await s.refresh(r_back)
            await s.refresh(r_front)
            task = Task(
                project_id=project.id, title="t", description="",
                state="in_progress",
            )
            s.add(task)
            await s.commit()
            await s.refresh(task)
            cwd_parent = tmp_path / "multi--feature"
            s.add(Worktree(
                repository_id=r_back.id, task_id=task.id,
                path=str(cwd_parent / "backend"), branch="feature",
            ))
            s.add(Worktree(
                repository_id=r_front.id, task_id=task.id,
                path=str(cwd_parent / "frontend"), branch="feature",
            ))
            await s.commit()
            cwd = await derive_run_cwd(s, task)
            assert cwd == cwd_parent
    finally:
        await db.close()

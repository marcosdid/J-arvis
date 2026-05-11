"""F6.a: RunInstance roundtrip + partial unique constraint (1 active per task)."""
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from orchestrator.store.database import Database
from orchestrator.store.models import Project, RunInstance, Task


@pytest.mark.integration
async def test_persist_and_query_run_instance(tmp_path: Path) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    await db.bootstrap()
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
                task_id=task.id,
                cwd=str(tmp_path / "p--feature"),
                manifest_path=str(tmp_path / "p" / ".orchestrator" / "run.yml"),
                network_name="jarvis-run-abc123",
                ports_json='{"backend": 31101, "frontend": 31102}',
                containers_json='{"backend": "cid-back", "frontend": "cid-front"}',
            )
            s.add(run)
            await s.commit()
            await s.refresh(run)
            run_id = run.id

        async with db.session() as s:
            rows = (await s.execute(select(RunInstance))).scalars().all()
            assert len(rows) == 1
            assert rows[0].id == run_id
            assert rows[0].status == "pending"
            assert rows[0].ports_json == '{"backend": 31101, "frontend": 31102}'
            assert rows[0].network_name == "jarvis-run-abc123"
            assert rows[0].started_at is not None
            assert rows[0].ended_at is None
            assert rows[0].error_message is None
    finally:
        await db.close()


@pytest.mark.integration
async def test_only_one_active_run_per_task(tmp_path: Path) -> None:
    """Partial unique index `ix_run_instances_active_task` blocks 2 active runs
    on the same task (both with ended_at IS NULL)."""
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    await db.bootstrap()
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

            # 1st active run — OK
            s.add(RunInstance(
                task_id=task.id, cwd="/x", manifest_path="/m",
                network_name="net1",
            ))
            await s.commit()

        async with db.session() as s:
            # 2nd active run on the same task — must violate the partial unique
            s.add(RunInstance(
                task_id=task.id, cwd="/y", manifest_path="/m",
                network_name="net2",
            ))
            with pytest.raises(IntegrityError):
                await s.commit()
    finally:
        await db.close()


@pytest.mark.integration
async def test_two_finished_runs_on_same_task_allowed(tmp_path: Path) -> None:
    """Once ended_at is set, the partial unique frees up — multiple historic
    runs per task is the expected accumulated audit trail."""
    from datetime import UTC, datetime

    db = Database(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    await db.bootstrap()
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

            s.add(RunInstance(
                task_id=task.id, cwd="/x", manifest_path="/m",
                network_name="net1",
                status="stopped",
                ended_at=datetime.now(UTC),
            ))
            s.add(RunInstance(
                task_id=task.id, cwd="/y", manifest_path="/m",
                network_name="net2",
                status="stopped",
                ended_at=datetime.now(UTC),
            ))
            await s.commit()  # both ended_at != NULL: partial unique doesn't fire

        async with db.session() as s:
            rows = (await s.execute(select(RunInstance))).scalars().all()
            assert len(rows) == 2
    finally:
        await db.close()

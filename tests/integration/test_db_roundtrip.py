from pathlib import Path

from sqlalchemy import select

from orchestrator.store.database import Database
from orchestrator.store.models import ClaudeSession, Project, Repository, Task, Worktree


async def test_persist_and_query_project_worktree_session(tmp_path: Path) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    await db.bootstrap()
    try:
        async with db.session() as s:
            project = Project(name="myrepo", path=str(tmp_path / "repo"))
            s.add(project)
            await s.commit()
            await s.refresh(project)

            repo = Repository(project_id=project.id, name="myrepo", sub_path=".")
            s.add(repo)
            await s.commit()
            await s.refresh(repo)

            task = Task(
                project_id=project.id,
                title="seed",
                description="",
                state="in_progress",
            )
            s.add(task)
            await s.commit()
            await s.refresh(task)

            worktree = Worktree(
                repository_id=repo.id,
                task_id=task.id,
                path=str(tmp_path / "repo"),
                branch="main",
            )
            s.add(worktree)
            await s.commit()
            await s.refresh(worktree)

            session_row = ClaudeSession(
                cwd=str(tmp_path / "repo"),
                task_id=task.id,
                status="executing",
            )
            s.add(session_row)
            await s.commit()
            await s.refresh(session_row)

            project_id = project.id
            session_id = session_row.id

        async with db.session() as s:
            projects = (await s.execute(select(Project))).scalars().all()
            assert len(projects) == 1
            assert projects[0].id == project_id
            assert projects[0].name == "myrepo"
            assert projects[0].created_at is not None

            sessions = (await s.execute(select(ClaudeSession))).scalars().all()
            assert len(sessions) == 1
            assert sessions[0].id == session_id
            assert sessions[0].status == "executing"
            assert sessions[0].started_at is not None
            assert sessions[0].ended_at is None
            assert sessions[0].pid is None
            assert sessions[0].jail_id is None
            assert sessions[0].transcript_path is None
    finally:
        await db.close()

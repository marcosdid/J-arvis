from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _uuid() -> str:
    return uuid4().hex


def _now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255))
    path: Mapped[str] = mapped_column(String(1024), unique=True)
    created_at: Mapped[datetime] = mapped_column(default=_now)


class Worktree(Base):
    __tablename__ = "worktrees"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    path: Mapped[str] = mapped_column(String(1024), unique=True)
    branch: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text(), nullable=False, default="")
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="idea")
    template: Mapped[str | None] = mapped_column(String(64), nullable=True)
    permission_profile: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_now)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)


class ClaudeSession(Base):
    """Persistent record of one Claude Code execution.

    Named ``ClaudeSession`` (not ``Session``) to avoid colliding with
    ``sqlalchemy.orm.Session`` and ``sqlalchemy.ext.asyncio.AsyncSession``
    in caller modules. The product concept is still ``session``; the table
    is ``sessions``. Each session belongs to exactly one ``Task`` via
    ``task_id`` (FK → tasks.id, ON DELETE RESTRICT).
    """

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    worktree_id: Mapped[str] = mapped_column(ForeignKey("worktrees.id"))
    task_id: Mapped[str] = mapped_column(
        ForeignKey("tasks.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32))
    pid: Mapped[int | None] = mapped_column(nullable=True)
    jail_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    transcript_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    started_at: Mapped[datetime] = mapped_column(default=_now)
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True)
    hook_token: Mapped[str | None] = mapped_column(String(32), nullable=True, unique=True)
    last_hook_at: Mapped[datetime | None] = mapped_column(nullable=True)

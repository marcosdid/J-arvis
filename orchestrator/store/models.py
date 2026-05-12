from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
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


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sub_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("project_id", "sub_path", name="uq_repo_project_subpath"),
    )


class Worktree(Base):
    __tablename__ = "worktrees"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    repository_id: Mapped[str] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[str | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
    )
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
    branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
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
    task_id: Mapped[str] = mapped_column(
        ForeignKey("tasks.id", ondelete="RESTRICT"), nullable=False
    )
    cwd: Mapped[str] = mapped_column(String(1024), nullable=False)
    status: Mapped[str] = mapped_column(String(32))
    pid: Mapped[int | None] = mapped_column(nullable=True)
    jail_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    transcript_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    started_at: Mapped[datetime] = mapped_column(default=_now)
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True)
    hook_token: Mapped[str | None] = mapped_column(String(32), nullable=True, unique=True)
    last_hook_at: Mapped[datetime | None] = mapped_column(nullable=True)


class RunInstance(Base):
    """One stack (db + services) brought up by F6 Run from Panel.

    Paralelo conceitual a ``ClaudeSession``: 1 RunInstance ativa por task
    (partial unique index ``ix_run_instances_active_task`` em ``task_id``
    WHERE ``ended_at IS NULL``). Cleanup quando task vira ``done``/``discarded``
    ou quando user clica Stop.

    ``ports_json``/``containers_json`` são JSON serializado (SQLite não tem
    tipo nativo). Schema esperado:
      ports_json: ``{"<service_name>": <host_port>, ...}``
      containers_json: ``{"<service_name>": "<docker_container_id>", ...}``
    """

    __tablename__ = "run_instances"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    cwd: Mapped[str] = mapped_column(String(1024), nullable=False)
    manifest_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    ports_json: Mapped[str] = mapped_column(Text(), nullable=False, default="{}")
    containers_json: Mapped[str] = mapped_column(Text(), nullable=False, default="{}")
    network_name: Mapped[str] = mapped_column(String(255), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)

    __table_args__ = (
        Index(
            "ix_run_instances_active_task",
            "task_id",
            unique=True,
            sqlite_where=text("ended_at IS NULL"),
        ),
    )


class MasterSession(Base):
    """Singleton: só pode existir 1 row com id='singleton'."""
    __tablename__ = "master_session"

    id: Mapped[str] = mapped_column(String, primary_key=True, default="singleton")
    claude_session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    pid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_active: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (
        CheckConstraint("id = 'singleton'", name="ck_master_singleton"),
    )

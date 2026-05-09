"""Roundtrip da migration 0003: upgrade → downgrade → upgrade."""
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def alembic_config(tmp_path: Path) -> Config:
    db_url = f"sqlite:///{tmp_path / 'roundtrip.db'}"
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _columns(engine, table: str) -> set[str]:
    return {c["name"] for c in inspect(engine).get_columns(table)}


@pytest.mark.integration
def test_migration_0003_roundtrip(alembic_config: Config) -> None:
    db_url = alembic_config.get_main_option("sqlalchemy.url")
    engine = create_engine(db_url)
    try:
        command.upgrade(alembic_config, "0003")
        assert "tasks" in inspect(engine).get_table_names()
        assert "task_id" in _columns(engine, "sessions")
        cols_after_up = _columns(engine, "sessions")

        command.downgrade(alembic_config, "0002")
        assert "tasks" not in inspect(engine).get_table_names()
        assert "task_id" not in _columns(engine, "sessions")

        command.upgrade(alembic_config, "0003")
        assert _columns(engine, "sessions") == cols_after_up
    finally:
        engine.dispose()

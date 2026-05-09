from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

RuntimeMode = Literal["aijail", "null"]


class Settings(BaseSettings):
    """Daemon settings, loaded from env vars with prefix ``JARVIS_``.

    - ``JARVIS_DATABASE_URL``: SQLAlchemy async URL. Defaults to local SQLite.
    - ``JARVIS_RUNTIME``: ``aijail`` (default, real) or ``null`` (E2E/dry-run).
    - ``JARVIS_UI_DIST``: path to the built UI bundle. If not a directory,
      static files are not mounted.
    """

    model_config = SettingsConfigDict(env_prefix="JARVIS_", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./jarvis.db"
    runtime: RuntimeMode = "aijail"
    ui_dist: Path = Path("/app/ui-dist")

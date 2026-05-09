from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

RuntimeMode = Literal["aijail", "null"]
NotifyMode = Literal["on", "off"]


class Settings(BaseSettings):
    """Daemon settings, loaded from env vars with prefix ``JARVIS_``.

    - ``JARVIS_DATABASE_URL``: SQLAlchemy async URL. Defaults to local SQLite.
    - ``JARVIS_RUNTIME``: ``aijail`` (default, real) or ``null`` (E2E/dry-run).
    - ``JARVIS_UI_DIST``: path to the built UI bundle. If not a directory,
      static files are not mounted.
    - ``JARVIS_PORT``: HTTP port the daemon listens on (used to derive the
      hook callback URL when ``hook_base_url`` is not set explicitly).
    - ``JARVIS_NOTIFY``: ``on`` enables desktop notifications via notify-send;
      ``off`` swaps to a no-op sink (for headless / CI runs).
    - ``JARVIS_HOOK_BASE_URL``: explicit override for the hook callback base
      URL injected into ``settings.json``. When unset, derived from ``port``.
    """

    model_config = SettingsConfigDict(env_prefix="JARVIS_", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./jarvis.db"
    runtime: RuntimeMode = "aijail"
    ui_dist: Path = Path("/app/ui-dist")
    port: int = 8765
    notify: NotifyMode = "on"
    hook_base_url: str | None = None

    @property
    def effective_hook_base_url(self) -> str:
        return self.hook_base_url or f"http://localhost:{self.port}"

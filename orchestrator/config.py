from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

RuntimeMode = Literal["aijail", "null"]
NotifyMode = Literal["on", "off"]

_REPO_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Daemon settings, loaded from env vars with prefix ``JARVIS_``.

    - ``JARVIS_DATABASE_URL``: SQLAlchemy async URL. Defaults to local SQLite.
    - ``JARVIS_RUNTIME``: ``aijail`` (default, real) or ``null`` (E2E/dry-run).
    - ``JARVIS_UI_DIST``: path to the built UI bundle. Default is the
      container path ``/app/ui-dist``; falls back to ``<repo>/ui/dist`` for
      host-development runs (after ``pnpm --dir ui run build``). If neither
      exists, static files are not mounted.
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

    @property
    def effective_ui_dist(self) -> Path | None:
        """First existing path from: explicit ``ui_dist``, then ``<repo>/ui/dist``.

        Lets the same daemon serve UI both in the container (``/app/ui-dist``,
        the default) and from a host checkout (``./ui/dist`` after ``pnpm
        run build``) without needing ``JARVIS_UI_DIST`` to be set manually.
        """
        if self.ui_dist.is_dir():
            return self.ui_dist
        fallback = _REPO_ROOT / "ui" / "dist"
        if fallback.is_dir():
            return fallback
        return None

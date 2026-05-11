"""F7.d: write_aijail_config consume claude_args + AiJailRuntime resolve catalog."""
from pathlib import Path

import pytest

from orchestrator.core.catalog import Catalog, load_catalog
from orchestrator.sandbox.aijail import (
    AiJailRuntime,
    PermissionProfileNotInCatalogError,
    write_aijail_config,
)


def _catalog() -> Catalog:
    repo_root = Path(__file__).resolve().parents[2]
    return load_catalog(repo_root / "orchestrator" / "config" / "catalog.yml")


class _FakeProcessOps:
    def __init__(self) -> None:
        self.spawns: list[tuple[list[str], str]] = []
        self.killed: list[int] = []

    def spawn(self, cmd: list[str], cwd: str) -> int:
        self.spawns.append((cmd, cwd))
        return 12345

    def kill(self, pid: int) -> None:
        self.killed.append(pid)


def test_write_aijail_config_yolo_args(tmp_path: Path) -> None:
    write_aijail_config(tmp_path, claude_args=["--dangerously-skip-permissions"])
    text = (tmp_path / ".ai-jail").read_text()
    assert 'command = ["claude", "--dangerously-skip-permissions"]' in text


def test_write_aijail_config_empty_args(tmp_path: Path) -> None:
    """Perfil `default` → command = ["claude"]."""
    write_aijail_config(tmp_path, claude_args=[])
    text = (tmp_path / ".ai-jail").read_text()
    assert 'command = ["claude"]' in text


def test_write_aijail_config_readonly_args(tmp_path: Path) -> None:
    write_aijail_config(
        tmp_path,
        claude_args=["--permission-mode", "plan", "--allowed-tools", "Read,Grep,Glob,LS"],
    )
    text = (tmp_path / ".ai-jail").read_text()
    assert ('command = ["claude", "--permission-mode", "plan", '
            '"--allowed-tools", "Read,Grep,Glob,LS"]') in text


def test_write_aijail_config_preserves_other_keys(tmp_path: Path) -> None:
    write_aijail_config(tmp_path, claude_args=[])
    text = (tmp_path / ".ai-jail").read_text()
    assert "rw_maps = " in text
    assert "ro_maps = []" in text
    assert "hide_dotdirs = []" in text
    assert "mask = []" in text
    assert "allow_tcp_ports = []" in text


async def test_aijail_runtime_spawn_resolves_profile(tmp_path: Path) -> None:
    ops = _FakeProcessOps()
    runtime = AiJailRuntime(lambda: "xterm", ops)
    handle = await runtime.spawn(
        tmp_path,
        permission_profile="read-only",
        catalog=_catalog(),
    )
    assert handle.pid == 12345
    text = (tmp_path / ".ai-jail").read_text()
    assert '"--permission-mode", "plan"' in text


async def test_aijail_runtime_spawn_none_uses_fallback(tmp_path: Path) -> None:
    """permission_profile=None → fallback do catalog (yolo no nosso catalog.yml)."""
    ops = _FakeProcessOps()
    runtime = AiJailRuntime(lambda: "xterm", ops)
    await runtime.spawn(
        tmp_path,
        permission_profile=None,
        catalog=_catalog(),
    )
    text = (tmp_path / ".ai-jail").read_text()
    assert '"--dangerously-skip-permissions"' in text


async def test_aijail_runtime_spawn_stale_profile_raises(tmp_path: Path) -> None:
    """Perfil removido do catalog → PermissionProfileNotInCatalogError."""
    ops = _FakeProcessOps()
    runtime = AiJailRuntime(lambda: "xterm", ops)
    with pytest.raises(PermissionProfileNotInCatalogError, match="ghost"):
        await runtime.spawn(
            tmp_path,
            permission_profile="ghost",
            catalog=_catalog(),
        )
    assert not (tmp_path / ".ai-jail").exists()
    assert ops.spawns == []

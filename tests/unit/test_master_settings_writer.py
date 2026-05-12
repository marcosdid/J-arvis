"""F8.b: writers do master settings.json + .ai-jail config."""
import json
from pathlib import Path

from orchestrator.sandbox.master_settings_writer import (
    write_master_aijail_config,
    write_master_settings,
)


def test_write_master_settings_produces_mcp_config(tmp_path: Path) -> None:
    write_master_settings(
        tmp_path, mcp_url="http://localhost:8765/api/mcp", token="testtoken123",
    )
    settings_path = tmp_path / ".claude" / "settings.json"
    assert settings_path.exists()
    data = json.loads(settings_path.read_text())
    assert "mcpServers" in data
    assert data["mcpServers"]["j-arvis-master"]["type"] == "http"
    assert data["mcpServers"]["j-arvis-master"]["url"] == "http://localhost:8765/api/mcp"
    assert data["mcpServers"]["j-arvis-master"]["headers"]["Authorization"] == "Bearer testtoken123"


def test_write_master_settings_no_hooks(tmp_path: Path) -> None:
    """Master NAO usa F2 hooks (decisao 9 da spec)."""
    write_master_settings(tmp_path, mcp_url="http://x/mcp", token="t")
    data = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    assert "hooks" not in data


def test_write_master_aijail_config_resumes_session(tmp_path: Path) -> None:
    write_master_aijail_config(tmp_path, claude_session_id="abc123", allow_port=8765)
    config_path = tmp_path / ".ai-jail"
    assert config_path.exists()
    text = config_path.read_text()
    assert '"--dangerously-skip-permissions"' in text
    assert '"--resume"' in text
    assert '"abc123"' in text
    assert "allow_tcp_ports = [8765]" in text

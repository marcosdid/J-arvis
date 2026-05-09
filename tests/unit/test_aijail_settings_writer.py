import json
from pathlib import Path

from orchestrator.sandbox.settings_writer import (
    build_settings_json,
    ensure_gitignore_entry,
    remove_settings_from_jail,
    write_settings_into_jail,
)


def test_build_settings_json_has_three_hooks() -> None:
    payload = build_settings_json(token="tok-abc", base_url="http://localhost:8765")
    parsed = json.loads(payload)
    assert set(parsed["hooks"]) == {"Notification", "PreToolUse", "Stop"}


def test_build_settings_json_embeds_token_and_base_url() -> None:
    payload = build_settings_json(token="tok-xyz", base_url="http://h:9000")
    cmd = json.loads(payload)["hooks"]["Notification"][0]["hooks"][0]["command"]
    assert "tok-xyz" in cmd
    assert "http://h:9000/api/hooks/Notification/tok-xyz" in cmd


def test_pretooluse_command_never_blocks() -> None:
    payload = build_settings_json(token="t", base_url="http://h:1")
    cmd = json.loads(payload)["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    assert cmd.endswith("; exit 0")


def test_write_settings_creates_file_inside_claude_dir(tmp_path: Path) -> None:
    write_settings_into_jail(tmp_path, token="t", base_url="http://h:1")
    settings = tmp_path / ".claude" / "settings.json"
    assert settings.is_file()
    parsed = json.loads(settings.read_text(encoding="utf-8"))
    assert "hooks" in parsed


def test_write_settings_overwrites_existing(tmp_path: Path) -> None:
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text("stale", encoding="utf-8")
    write_settings_into_jail(tmp_path, token="t", base_url="http://h:1")
    parsed = json.loads(settings.read_text(encoding="utf-8"))
    assert "hooks" in parsed


def test_ensure_gitignore_entry_appends_when_missing(tmp_path: Path) -> None:
    ensure_gitignore_entry(tmp_path)
    content = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert ".claude/settings.json" in content


def test_ensure_gitignore_entry_idempotent(tmp_path: Path) -> None:
    ensure_gitignore_entry(tmp_path)
    ensure_gitignore_entry(tmp_path)
    content = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert content.count(".claude/settings.json") == 1


def test_ensure_gitignore_creates_file_when_absent(tmp_path: Path) -> None:
    assert not (tmp_path / ".gitignore").exists()
    ensure_gitignore_entry(tmp_path)
    assert (tmp_path / ".gitignore").is_file()


def test_remove_settings_silently_ok_when_absent(tmp_path: Path) -> None:
    remove_settings_from_jail(tmp_path)


def test_remove_settings_removes_file_when_present(tmp_path: Path) -> None:
    write_settings_into_jail(tmp_path, token="t", base_url="http://h:1")
    remove_settings_from_jail(tmp_path)
    assert not (tmp_path / ".claude" / "settings.json").exists()

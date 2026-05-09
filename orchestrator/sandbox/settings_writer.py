"""Writes ``.claude/settings.json`` into the worktree before ``ai-jail run``."""

import json
from pathlib import Path

_GITIGNORE_LINE = ".claude/settings.json"


def build_settings_json(*, token: str, base_url: str) -> str:
    def hook(event: str, *, terminator: str = "") -> dict[str, object]:
        return {
            "matcher": "*",
            "hooks": [
                {
                    "type": "command",
                    "command": (
                        f"curl -sS -X POST '{base_url}/api/hooks/{event}/{token}' "
                        f"--data-binary @-{terminator}"
                    ),
                }
            ],
        }

    payload = {
        "hooks": {
            "Notification": [hook("Notification")],
            "PreToolUse": [hook("PreToolUse", terminator="; exit 0")],
            "Stop": [hook("Stop")],
        }
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def write_settings_into_jail(worktree: Path, *, token: str, base_url: str) -> None:
    target = worktree / ".claude" / "settings.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(build_settings_json(token=token, base_url=base_url), encoding="utf-8")
    target.chmod(0o644)


def remove_settings_from_jail(worktree: Path) -> None:
    target = worktree / ".claude" / "settings.json"
    target.unlink(missing_ok=True)


def ensure_gitignore_entry(worktree: Path) -> None:
    path = worktree / ".gitignore"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = existing.splitlines()
    if _GITIGNORE_LINE in lines:
        return
    suffix = "" if existing.endswith("\n") or not existing else "\n"
    path.write_text(existing + suffix + _GITIGNORE_LINE + "\n", encoding="utf-8")

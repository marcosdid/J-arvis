"""Pure functions that translate hook payloads into domain decisions."""

from typing import Any

from orchestrator.core.sessions import SessionStatus


class InvalidHookPayloadError(Exception):
    pass


def parse_notification(payload: dict[str, Any]) -> SessionStatus:
    if "message" not in payload:
        raise InvalidHookPayloadError("Notification payload missing 'message'")
    return SessionStatus.AWAITING_RESPONSE


def parse_stop(_payload: dict[str, Any]) -> SessionStatus:
    return SessionStatus.IDLE


def parse_pretooluse(payload: dict[str, Any]) -> str:
    tool = payload.get("tool_name")
    if not isinstance(tool, str) or not tool:
        raise InvalidHookPayloadError("PreToolUse payload missing 'tool_name'")
    return tool

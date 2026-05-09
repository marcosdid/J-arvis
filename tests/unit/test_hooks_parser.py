import pytest

from orchestrator.core.sessions import SessionStatus
from orchestrator.hooks.parser import (
    InvalidHookPayloadError,
    parse_notification,
    parse_pretooluse,
    parse_stop,
)


def test_parse_notification_returns_awaiting_response() -> None:
    payload = {"message": "Claude needs your input"}
    assert parse_notification(payload) == SessionStatus.AWAITING_RESPONSE


def test_parse_notification_missing_message_raises() -> None:
    with pytest.raises(InvalidHookPayloadError):
        parse_notification({})


def test_parse_stop_returns_idle() -> None:
    assert parse_stop({"reason": "turn-end"}) == SessionStatus.IDLE


def test_parse_pretooluse_returns_tool_name() -> None:
    payload = {"tool_name": "Bash", "tool_input": {"command": "ls"}}
    assert parse_pretooluse(payload) == "Bash"


def test_parse_pretooluse_missing_tool_name_raises() -> None:
    with pytest.raises(InvalidHookPayloadError):
        parse_pretooluse({})

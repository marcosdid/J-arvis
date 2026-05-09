import pytest

from orchestrator.core.sessions import SessionStatus
from orchestrator.notifications.sink import should_notify


@pytest.mark.parametrize("prev", [SessionStatus.EXECUTING, SessionStatus.IDLE])
def test_should_notify_when_transitioning_to_awaiting_response(prev: SessionStatus) -> None:
    assert should_notify(prev, SessionStatus.AWAITING_RESPONSE) is True


@pytest.mark.parametrize("prev", [SessionStatus.EXECUTING, SessionStatus.AWAITING_RESPONSE])
def test_should_notify_when_transitioning_to_idle(prev: SessionStatus) -> None:
    assert should_notify(prev, SessionStatus.IDLE) is True


@pytest.mark.parametrize(
    "new",
    [SessionStatus.EXECUTING, SessionStatus.DONE, SessionStatus.ERROR, SessionStatus.AWAITING_APPROVAL],
)
def test_should_not_notify_for_other_targets(new: SessionStatus) -> None:
    assert should_notify(SessionStatus.IDLE, new) is False


def test_should_not_notify_on_idempotent_transition() -> None:
    assert should_notify(SessionStatus.IDLE, SessionStatus.IDLE) is False
    assert should_notify(SessionStatus.AWAITING_RESPONSE, SessionStatus.AWAITING_RESPONSE) is False

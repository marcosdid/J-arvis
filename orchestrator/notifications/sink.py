"""Notification policy + Protocol."""

from typing import Protocol

from orchestrator.core.sessions import SessionStatus

_NOTIFY_TARGETS = frozenset({SessionStatus.AWAITING_RESPONSE, SessionStatus.IDLE})


def should_notify(previous: SessionStatus, new: SessionStatus) -> bool:
    if previous == new:
        return False
    return new in _NOTIFY_TARGETS


class NotifierSink(Protocol):
    async def notify(self, *, summary: str, body: str, icon: str) -> None: ...

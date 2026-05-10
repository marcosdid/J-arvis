import pytest

from orchestrator.events.broadcaster import InMemoryWsBroadcaster
from orchestrator.events.envelope import WsEvent


class FakeWebSocket:
    def __init__(self, *, fail: bool = False) -> None:
        self.received: list[dict[str, object]] = []
        self._fail = fail

    async def send_json(self, data: dict[str, object]) -> None:
        if self._fail:
            raise RuntimeError("client gone")
        self.received.append(data)


@pytest.mark.asyncio
async def test_publish_to_no_clients_is_noop() -> None:
    bc = InMemoryWsBroadcaster()
    await bc.publish(WsEvent.session_stopped(session_id="x", task_id="t1"))


@pytest.mark.asyncio
async def test_publish_fans_out_to_all_subscribers() -> None:
    bc = InMemoryWsBroadcaster()
    a, b = FakeWebSocket(), FakeWebSocket()
    bc.subscribe(a)
    bc.subscribe(b)
    await bc.publish(WsEvent.session_stopped(session_id="x", task_id="t1"))
    assert len(a.received) == 1
    assert len(b.received) == 1


@pytest.mark.asyncio
async def test_failing_subscriber_is_dropped() -> None:
    bc = InMemoryWsBroadcaster()
    bad = FakeWebSocket(fail=True)
    good = FakeWebSocket()
    bc.subscribe(bad)
    bc.subscribe(good)
    await bc.publish(WsEvent.session_stopped(session_id="x", task_id="t1"))
    assert len(good.received) == 1
    assert bad not in bc.subscribers


@pytest.mark.asyncio
async def test_unsubscribe_removes_client() -> None:
    bc = InMemoryWsBroadcaster()
    a = FakeWebSocket()
    bc.subscribe(a)
    bc.unsubscribe(a)
    await bc.publish(WsEvent.session_stopped(session_id="x", task_id="t1"))
    assert a.received == []

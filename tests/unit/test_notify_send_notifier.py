import pytest

from orchestrator.notifications.notify_send import NoopNotifier, NotifySendNotifier


class FakeRunner:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls: list[list[str]] = []
        self._fail = fail

    async def run(self, argv: list[str]) -> None:
        self.calls.append(argv)
        if self._fail:
            raise FileNotFoundError("notify-send")


@pytest.mark.asyncio
async def test_notify_send_invokes_command() -> None:
    runner = FakeRunner()
    notifier = NotifySendNotifier(runner=runner)
    await notifier.notify(
        summary="J-arvis · main", body="Aguarda você", icon="dialog-information"
    )
    assert runner.calls == [
        ["notify-send", "--icon=dialog-information", "J-arvis · main", "Aguarda você"]
    ]


@pytest.mark.asyncio
async def test_notify_send_swallows_filenotfound() -> None:
    runner = FakeRunner(fail=True)
    notifier = NotifySendNotifier(runner=runner)
    await notifier.notify(summary="x", body="y", icon="i")
    await notifier.notify(summary="x", body="y", icon="i")
    assert len(runner.calls) == 2  # both attempts ran; failures didn't crash


@pytest.mark.asyncio
async def test_noop_notifier_does_nothing() -> None:
    await NoopNotifier().notify(summary="x", body="y", icon="i")

"""F6.h: watch_for_manifest — polling do .orchestrator/run.yml."""
import asyncio
from pathlib import Path

import pytest

from orchestrator.core.bootstrap import watch_for_manifest
from orchestrator.events.envelope import WsEvent


class CollectingBroadcaster:
    def __init__(self) -> None:
        self.events: list[WsEvent] = []

    async def publish(self, event: WsEvent) -> None:
        self.events.append(event)


@pytest.mark.unit
async def test_watch_returns_false_on_timeout(tmp_path: Path) -> None:
    """Arquivo nunca aparece → após max_attempts retorna False sem broadcast."""
    bc = CollectingBroadcaster()
    detected = await watch_for_manifest(
        tmp_path, bc, interval=0.005, max_attempts=3,
    )
    assert detected is False
    assert bc.events == []


@pytest.mark.unit
async def test_watch_returns_true_and_broadcasts_when_manifest_appears(
    tmp_path: Path,
) -> None:
    """Arquivo aparece após 1 poll → detect + broadcast com conteúdo."""
    bc = CollectingBroadcaster()
    target_dir = tmp_path / ".orchestrator"
    target_dir.mkdir()
    target = target_dir / "run.yml"

    async def create_after_delay() -> None:
        await asyncio.sleep(0.02)
        target.write_text("version: '1'\nservices: {a: {image: x}}")

    _task = asyncio.create_task(create_after_delay())  # noqa: RUF006 — owned by test scope
    detected = await watch_for_manifest(
        tmp_path, bc, interval=0.005, max_attempts=20,
    )
    assert detected is True
    assert len(bc.events) == 1
    assert bc.events[0].type == "bootstrap.proposed"
    assert "version: '1'" in bc.events[0].payload["manifest_text"]
    assert bc.events[0].task_id is None  # bootstrap não é vinculado a task


@pytest.mark.unit
async def test_watch_broadcasts_only_once_when_file_present_at_first_poll(
    tmp_path: Path,
) -> None:
    """Se arquivo já existe quando watcher inicia, broadcasta no 1º poll
    e retorna — não fica em loop."""
    bc = CollectingBroadcaster()
    (tmp_path / ".orchestrator").mkdir()
    (tmp_path / ".orchestrator" / "run.yml").write_text("version: '1'\nservices: {}")
    detected = await watch_for_manifest(
        tmp_path, bc, interval=0.005, max_attempts=10,
    )
    assert detected is True
    assert len(bc.events) == 1

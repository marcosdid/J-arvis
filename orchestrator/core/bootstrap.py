"""F6.h bootstrap — polling watcher pra `<project>/.orchestrator/run.yml`.

Sessão Claude efêmera spawnada via `AiJailRuntime.spawn(project_path)` —
não persiste como `ClaudeSession`, não tem `task_id`. O sinal de
"manifesto pronto" vem do filesystem: watcher polla a cada N segundos
até detectar o arquivo OU até timeout.
"""
import asyncio
import logging
from pathlib import Path

from orchestrator.events.broadcaster import WsBroadcaster
from orchestrator.events.envelope import WsEvent

_log = logging.getLogger(__name__)


async def watch_for_manifest(
    project_path: Path,
    broadcaster: WsBroadcaster,
    *,
    interval: float = 2.0,
    max_attempts: int = 900,
) -> bool:
    """Polla `<project_path>/.orchestrator/run.yml` até detectar ou timeout.

    Quando detecta, broadcasta `bootstrap.proposed` com o conteúdo do
    arquivo. Retorna `True` se detectou, `False` se timeout.

    Defaults: 2s * 900 = 30min total. Pra testes, override com
    interval=0.01 + max_attempts=10.
    """
    target = project_path / ".orchestrator" / "run.yml"
    for _ in range(max_attempts):
        await asyncio.sleep(interval)
        if target.exists():
            try:
                manifest_text = target.read_text()
            except OSError as e:  # pragma: no cover — race com delete
                _log.warning("watch_for_manifest: read failed: %s", e)
                return False
            await broadcaster.publish(
                WsEvent.bootstrap_proposed(manifest_text=manifest_text),
            )
            return True
    return False


__all__ = ["watch_for_manifest"]

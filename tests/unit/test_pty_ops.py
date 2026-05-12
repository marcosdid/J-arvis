"""F8.a: stub tests garantem que Protocol + dataclass têm os métodos certos."""
import dataclasses
from datetime import UTC, datetime

import pytest

from orchestrator.sandbox.pty_runtime import MasterPtyHandle, PtyProcessOps


def test_pty_process_ops_declares_required_methods() -> None:
    """Verifica que Protocol expõe a API esperada (spawn/read/write/resize/kill/close)."""
    required = {"spawn", "read", "write", "resize", "kill", "close"}
    actual = {name for name in dir(PtyProcessOps) if not name.startswith("_")}
    assert required.issubset(actual)


def test_master_pty_handle_constructs() -> None:
    h = MasterPtyHandle(
        pid=1234,
        master_fd=7,
        claude_session_id="abc123",
        started_at=datetime.now(UTC),
    )
    assert h.pid == 1234
    assert h.claude_session_id == "abc123"


def test_master_pty_handle_is_frozen() -> None:
    """Dataclass deve ser frozen pra imutabilidade."""
    h = MasterPtyHandle(
        pid=1, master_fd=2, claude_session_id="x", started_at=datetime.now(UTC),
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        h.pid = 999  # type: ignore[misc]

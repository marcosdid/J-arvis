from pathlib import Path

import pytest

from orchestrator.sandbox.null import NullSessionRuntime
from orchestrator.sandbox.runtime import JailHandle


@pytest.mark.unit
async def test_null_runtime_spawn_returns_handle_with_positive_pid() -> None:
    runtime = NullSessionRuntime()
    handle = await runtime.spawn(Path("/tmp"))

    assert isinstance(handle, JailHandle)
    assert handle.pid > 0
    assert handle.id


@pytest.mark.unit
async def test_null_runtime_spawn_yields_unique_handles() -> None:
    runtime = NullSessionRuntime()
    first = await runtime.spawn(Path("/tmp/a"))
    second = await runtime.spawn(Path("/tmp/b"))

    assert first.id != second.id
    assert first.pid != second.pid


@pytest.mark.unit
async def test_null_runtime_kill_is_noop() -> None:
    runtime = NullSessionRuntime()
    handle = await runtime.spawn(Path("/tmp"))
    await runtime.kill(handle)  # must not raise

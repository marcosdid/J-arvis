import pytest

from orchestrator.main import build_runtime
from orchestrator.sandbox.aijail import AiJailRuntime
from orchestrator.sandbox.null import NullSessionRuntime


@pytest.mark.unit
def test_build_runtime_aijail() -> None:
    assert isinstance(build_runtime("aijail"), AiJailRuntime)


@pytest.mark.unit
def test_build_runtime_null() -> None:
    assert isinstance(build_runtime("null"), NullSessionRuntime)

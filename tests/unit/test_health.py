import pytest

from orchestrator.core.health import health_status


@pytest.mark.unit
def test_health_status_returns_ok() -> None:
    assert health_status() == "ok"

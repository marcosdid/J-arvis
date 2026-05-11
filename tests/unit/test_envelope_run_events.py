"""F6 (parte de F6.g): factories WS pros eventos run.* + bootstrap.proposed."""
import pytest

from orchestrator.events.envelope import WsEvent


@pytest.mark.unit
def test_run_status_factory() -> None:
    e = WsEvent.run_status(
        task_id="t1", run_id="r1", status="building",
        services=[{"name": "db", "state": "building", "port_host": None,
                   "port_container": 5432, "container_id": None, "error": None}],
    )
    assert e.type == "run.status"
    assert e.task_id == "t1"
    assert e.session_id == ""
    assert e.payload["run_id"] == "r1"
    assert e.payload["status"] == "building"
    assert e.payload["services"][0]["name"] == "db"
    assert e.at is not None


@pytest.mark.unit
def test_run_status_default_empty_services() -> None:
    e = WsEvent.run_status(task_id="t1", run_id="r1", status="pending")
    assert e.payload["services"] == []


@pytest.mark.unit
def test_run_failed_factory_with_service() -> None:
    e = WsEvent.run_failed(
        task_id="t1", run_id="r1", service="backend",
        error="build failed: no dockerfile",
    )
    assert e.type == "run.failed"
    assert e.payload["service"] == "backend"
    assert "build failed" in e.payload["error"]


@pytest.mark.unit
def test_run_failed_factory_without_service() -> None:
    e = WsEvent.run_failed(
        task_id="t1", run_id="r1", service=None,
        error="network create failed",
    )
    assert e.payload["service"] is None


@pytest.mark.unit
def test_run_stopped_factory_reasons() -> None:
    for reason in ("manual", "session_stopped", "task_terminal"):
        e = WsEvent.run_stopped(task_id="t1", run_id="r1", reason=reason)
        assert e.type == "run.stopped"
        assert e.payload["reason"] == reason


@pytest.mark.unit
def test_bootstrap_proposed_no_task_id() -> None:
    """Bootstrap é sessão efêmera não-vinculada a task → task_id é None."""
    e = WsEvent.bootstrap_proposed(manifest_text="version: '1'\nservices: {}")
    assert e.type == "bootstrap.proposed"
    assert e.task_id is None
    assert e.session_id == ""
    assert "version" in e.payload["manifest_text"]

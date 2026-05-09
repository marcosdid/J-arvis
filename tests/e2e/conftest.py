from collections.abc import Generator
from pathlib import Path

import pytest
from testcontainers.core.container import DockerContainer
from testcontainers.core.image import DockerImage
from testcontainers.core.wait_strategies import LogMessageWaitStrategy

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def orchestrator_image() -> Generator[DockerImage]:
    image = DockerImage(
        path=str(PROJECT_ROOT),
        tag="j-arvis-orchestrator:e2e",
        dockerfile_path="Dockerfile.orchestrator",
    )
    image.build()
    yield image


@pytest.fixture(scope="session")
def orchestrator_url(orchestrator_image: DockerImage) -> Generator[str]:
    wait = LogMessageWaitStrategy("Application startup complete").with_startup_timeout(120)
    container = (
        DockerContainer(str(orchestrator_image))
        .with_exposed_ports(8000)
        .waiting_for(wait)
    )
    try:
        container.start()
        host = container.get_container_host_ip()
        port = container.get_exposed_port(8000)
        yield f"http://{host}:{port}"
    finally:
        container.stop()

from collections.abc import Generator
from pathlib import Path

import pytest
from testcontainers.core.container import DockerContainer
from testcontainers.core.image import DockerImage
from testcontainers.core.wait_strategies import HealthcheckWaitStrategy

PROJECT_ROOT = Path(__file__).resolve().parents[2]


_INIT_REPO_SCRIPT = r"""
set -e
mkdir -p /tmp/repos/main
cd /tmp/repos/main
git init -b main >/dev/null
echo hi > README.md
git config user.email t@example.com
git config user.name t
git -c commit.gpgsign=false add README.md
git -c commit.gpgsign=false commit -m init >/dev/null
git worktree add /tmp/repos/feature -b feature >/dev/null
"""


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
    wait = HealthcheckWaitStrategy().with_startup_timeout(120)
    container = (
        DockerContainer(str(orchestrator_image))
        .with_exposed_ports(8000)
        .with_env("JARVIS_RUNTIME", "null")
        .with_env("JARVIS_DEBUG", "1")
        .waiting_for(wait)
    )
    try:
        container.start()
        host = container.get_container_host_ip()
        port = container.get_exposed_port(8000)
        yield f"http://{host}:{port}"
    finally:
        container.stop()


@pytest.fixture
def orchestrator_with_repo(
    orchestrator_image: DockerImage,
) -> Generator[tuple[str, str]]:
    """Start a fresh container and create a git repo inside it via container.exec.

    Avoids host UID (1001) vs container jarvis user (1000) mismatch that
    breaks bind-mounted tmp_path; the daemon needs to read the repo files.
    """
    wait = HealthcheckWaitStrategy().with_startup_timeout(120)
    container = (
        DockerContainer(str(orchestrator_image))
        .with_exposed_ports(8000)
        .with_env("JARVIS_RUNTIME", "null")
        .with_env("JARVIS_DEBUG", "1")
        .waiting_for(wait)
    )
    try:
        container.start()
        result = container.exec(["sh", "-c", _INIT_REPO_SCRIPT])
        assert result.exit_code == 0, result.output
        host = container.get_container_host_ip()
        port = container.get_exposed_port(8000)
        yield f"http://{host}:{port}", "/tmp/repos/main"
    finally:
        container.stop()

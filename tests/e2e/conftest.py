from collections.abc import Generator
from pathlib import Path

import pytest
from testcontainers.core.container import DockerContainer
from testcontainers.core.image import DockerImage
from testcontainers.core.wait_strategies import HealthcheckWaitStrategy

PROJECT_ROOT = Path(__file__).resolve().parents[2]


# All init scripts end with `chown -R 1000:1000 /tmp/repos` so the daemon
# (running as `jarvis` UID 1000 — see Dockerfile.orchestrator) can write
# inside /tmp/repos/ when F5 creates worktrees via `git worktree add` from
# a sibling path (e.g. /tmp/repos/main--add-login).

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
chown -R 1000:1000 /tmp/repos
"""


_INIT_MULTI_REPO_SCRIPT = r"""
set -e
mkdir -p /tmp/repos/multi/backend /tmp/repos/multi/frontend
for sub in backend frontend; do
  cd /tmp/repos/multi/$sub
  git init -b main >/dev/null
  echo "hi from $sub" > README.md
  git config user.email t@example.com
  git config user.name t
  git -c commit.gpgsign=false add README.md
  git -c commit.gpgsign=false commit -m init >/dev/null
done
chown -R 1000:1000 /tmp/repos
"""


_INIT_REPO_WITH_EXTERNAL_WT_SCRIPT = r"""
set -e
mkdir -p /tmp/repos/withorphan
cd /tmp/repos/withorphan
git init -b main >/dev/null
echo hi > README.md
git config user.email t@example.com
git config user.name t
git -c commit.gpgsign=false add README.md
git -c commit.gpgsign=false commit -m init >/dev/null
git worktree add /tmp/repos/withorphan-external -b external >/dev/null
chown -R 1000:1000 /tmp/repos
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


def _start_with_init_script(
    image: DockerImage, init_script: str
) -> DockerContainer:
    """Start a fresh container with the daemon, then seed git state via init_script.

    Avoids host UID (1001) vs container jarvis user (1000) mismatch that
    breaks bind-mounted tmp_path; the daemon needs to read the repo files.
    """
    wait = HealthcheckWaitStrategy().with_startup_timeout(120)
    container = (
        DockerContainer(str(image))
        .with_exposed_ports(8000)
        .with_env("JARVIS_RUNTIME", "null")
        .with_env("JARVIS_DEBUG", "1")
        .waiting_for(wait)
    )
    container.start()
    result = container.exec(["sh", "-c", init_script])
    assert result.exit_code == 0, result.output
    return container


@pytest.fixture
def orchestrator_with_repo(
    orchestrator_image: DockerImage,
) -> Generator[tuple[str, str]]:
    """Monorepo at /tmp/repos/main with a pre-existing `feature` worktree."""
    container = _start_with_init_script(orchestrator_image, _INIT_REPO_SCRIPT)
    try:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(8000)
        yield f"http://{host}:{port}", "/tmp/repos/main"
    finally:
        container.stop()


@pytest.fixture
def orchestrator_with_multi_repo(
    orchestrator_image: DockerImage,
) -> Generator[tuple[str, str]]:
    """Multi-repo at /tmp/repos/multi/{backend,frontend} (each its own .git).

    Used by F5 multi-repo flow: 1 task spawns N worktrees (one per sub-repo)."""
    container = _start_with_init_script(orchestrator_image, _INIT_MULTI_REPO_SCRIPT)
    try:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(8000)
        yield f"http://{host}:{port}", "/tmp/repos/multi"
    finally:
        container.stop()


@pytest.fixture
def orchestrator_with_external_worktree(
    orchestrator_image: DockerImage,
) -> Generator[tuple[str, str]]:
    """Monorepo at /tmp/repos/withorphan with an externally-created worktree.

    After the project is added via UI, the external worktree shows up as
    an órfã (task_id NULL) under the project node."""
    container = _start_with_init_script(
        orchestrator_image, _INIT_REPO_WITH_EXTERNAL_WT_SCRIPT
    )
    try:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(8000)
        yield f"http://{host}:{port}", "/tmp/repos/withorphan"
    finally:
        container.stop()

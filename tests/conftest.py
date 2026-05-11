"""Auto-marker shared across the test tree.

Tests under ``tests/unit/``, ``tests/integration/`` and ``tests/e2e/`` get
the matching pytest marker applied automatically based on their path.

Without this, files that forget ``pytestmark = pytest.mark.unit`` (or the
per-test decorator) are silently deselected by ``-m "unit or integration"``,
which lowers effective coverage below the gate without surfacing in the
test output. See gotchas.md #11.
"""

from functools import lru_cache
from pathlib import Path

import pytest

from orchestrator.core.catalog import Catalog, load_catalog

_TESTS_ROOT = Path(__file__).parent
_REPO_ROOT_FOR_CATALOG = _TESTS_ROOT.parent

_MARK_BY_DIR: dict[str, pytest.MarkDecorator] = {
    "unit": pytest.mark.unit,
    "integration": pytest.mark.integration,
    "e2e": pytest.mark.e2e,
}


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    for item in items:
        rel = Path(item.fspath).resolve().relative_to(_TESTS_ROOT)
        first = rel.parts[0] if rel.parts else ""
        marker = _MARK_BY_DIR.get(first)
        if marker is not None:
            item.add_marker(marker)


@lru_cache(maxsize=1)
def _get_test_catalog() -> Catalog:
    return load_catalog(_REPO_ROOT_FOR_CATALOG / "orchestrator" / "config" / "catalog.yml")


@pytest.fixture
def catalog() -> Catalog:
    """Pytest fixture exposing the real catalog.yml for tests that call
    `create_task` or `start_session` directly (bypassing the API DI)."""
    return _get_test_catalog()

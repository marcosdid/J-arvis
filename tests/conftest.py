"""Auto-marker shared across the test tree.

Tests under ``tests/unit/``, ``tests/integration/`` and ``tests/e2e/`` get
the matching pytest marker applied automatically based on their path.

Without this, files that forget ``pytestmark = pytest.mark.unit`` (or the
per-test decorator) are silently deselected by ``-m "unit or integration"``,
which lowers effective coverage below the gate without surfacing in the
test output. See gotchas.md #11.
"""

from pathlib import Path

import pytest

_TESTS_ROOT = Path(__file__).parent

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

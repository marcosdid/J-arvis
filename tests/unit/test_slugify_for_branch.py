import pytest

from orchestrator.core.slug import (
    InvalidBranchSlugError,
    slugify_for_branch,
)


def test_simple() -> None:
    assert slugify_for_branch("Add dark mode") == "add-dark-mode"


def test_collapses_repeated_separators() -> None:
    assert slugify_for_branch("Refactor:::HTTP/2 layer") == "refactor-http-2-layer"


def test_strips_leading_trailing() -> None:
    assert slugify_for_branch("  --  Fix bug  --  ") == "fix-bug"


def test_truncates_at_60() -> None:
    long = "a" * 100
    assert len(slugify_for_branch(long)) == 60


def test_unicode_collapses_to_hyphens() -> None:
    # accents are non-[a-z0-9] -> become hyphens, then collapsed
    assert slugify_for_branch("Café à la mode") == "caf-la-mode"


def test_empty_raises() -> None:
    with pytest.raises(InvalidBranchSlugError):
        slugify_for_branch("...")


def test_only_whitespace_raises() -> None:
    with pytest.raises(InvalidBranchSlugError):
        slugify_for_branch("   ")

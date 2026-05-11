"""F7.a: Pydantic Catalog + load_catalog."""
from pathlib import Path

import pytest

from orchestrator.core.catalog import (
    Catalog,
    CatalogValidationError,
    load_catalog,
)


_VALID_YAML = """
version: "1"
fallback_permission_profile: yolo
permission_profiles:
  yolo: {description: "Y", claude_args: ["--dangerously-skip-permissions"]}
  default: {description: "D", claude_args: []}
templates:
  frontend:
    description: "F"
    default_permission_profile: yolo
    branch_prefix: "feat-ui/"
"""


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "catalog.yml"
    p.write_text(body)
    return p


def test_load_valid_catalog(tmp_path: Path) -> None:
    cat = load_catalog(_write(tmp_path, _VALID_YAML))
    assert isinstance(cat, Catalog)
    assert cat.fallback_permission_profile == "yolo"
    assert "yolo" in cat.permission_profiles
    assert cat.templates["frontend"].branch_prefix == "feat-ui/"


def test_fallback_dangling_raises(tmp_path: Path) -> None:
    bad = _VALID_YAML.replace("fallback_permission_profile: yolo",
                              "fallback_permission_profile: ghost")
    with pytest.raises(CatalogValidationError, match="fallback"):
        load_catalog(_write(tmp_path, bad))


def test_template_default_profile_dangling_raises(tmp_path: Path) -> None:
    bad = _VALID_YAML.replace("default_permission_profile: yolo",
                              "default_permission_profile: ghost")
    with pytest.raises(CatalogValidationError, match="ghost"):
        load_catalog(_write(tmp_path, bad))


def test_extra_field_forbidden(tmp_path: Path) -> None:
    bad = _VALID_YAML.replace("templates:", "extra_field: 42\ntemplates:")
    with pytest.raises(Exception, match="extra"):  # ValidationError
        load_catalog(_write(tmp_path, bad))


def test_branch_prefix_without_slash_rejected(tmp_path: Path) -> None:
    bad = _VALID_YAML.replace('branch_prefix: "feat-ui/"',
                              'branch_prefix: "feat-ui"')
    with pytest.raises(Exception, match="branch_prefix|pattern"):
        load_catalog(_write(tmp_path, bad))


def test_branch_prefix_multi_segment_rejected(tmp_path: Path) -> None:
    bad = _VALID_YAML.replace('branch_prefix: "feat-ui/"',
                              'branch_prefix: "feat/ui/"')
    with pytest.raises(Exception, match="branch_prefix|pattern"):
        load_catalog(_write(tmp_path, bad))


def test_version_must_be_1(tmp_path: Path) -> None:
    bad = _VALID_YAML.replace('version: "1"', 'version: "2"')
    with pytest.raises(Exception, match="version"):
        load_catalog(_write(tmp_path, bad))


def test_profile_name_must_match_regex(tmp_path: Path) -> None:
    bad = _VALID_YAML.replace("yolo:", "Yolo:")
    with pytest.raises(CatalogValidationError, match="name"):
        load_catalog(_write(tmp_path, bad))


def test_template_name_must_match_regex(tmp_path: Path) -> None:
    bad = _VALID_YAML.replace("frontend:", "FrontEnd:")
    with pytest.raises(CatalogValidationError, match="name"):
        load_catalog(_write(tmp_path, bad))


def test_load_nonexistent_path_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_catalog(tmp_path / "nope.yml")


def test_real_catalog_yml_is_valid() -> None:
    """A fonte curada em orchestrator/config/catalog.yml deve carregar
    sem erros. Caso contrário daemon não sobe."""
    repo_root = Path(__file__).resolve().parents[2]
    cat = load_catalog(repo_root / "orchestrator" / "config" / "catalog.yml")
    assert set(cat.templates.keys()) == {"frontend", "backend", "refactor", "bugfix"}
    assert set(cat.permission_profiles.keys()) == {"yolo", "default", "read-only"}
    assert cat.fallback_permission_profile == "yolo"

from pathlib import Path

from orchestrator.config import Settings


def test_effective_hook_base_url_falls_back_to_port() -> None:
    settings = Settings(port=4242)
    assert settings.effective_hook_base_url == "http://localhost:4242"


def test_effective_hook_base_url_explicit_override_wins() -> None:
    settings = Settings(hook_base_url="http://elsewhere:9000", port=4242)
    assert settings.effective_hook_base_url == "http://elsewhere:9000"


def test_effective_ui_dist_returns_explicit_when_exists(tmp_path: Path) -> None:
    settings = Settings(ui_dist=tmp_path)
    assert settings.effective_ui_dist == tmp_path


def test_effective_ui_dist_falls_back_to_repo_ui_dist_when_explicit_missing(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "does-not-exist"
    repo_dist = Path(__file__).resolve().parents[2] / "ui" / "dist"
    settings = Settings(ui_dist=missing)
    if repo_dist.is_dir():
        assert settings.effective_ui_dist == repo_dist
    else:
        assert settings.effective_ui_dist is None


def test_effective_ui_dist_returns_none_when_nothing_exists(
    tmp_path: Path, monkeypatch
) -> None:
    missing = tmp_path / "does-not-exist"
    settings = Settings(ui_dist=missing)
    fake_repo = tmp_path / "fake-repo"
    monkeypatch.setattr("orchestrator.config._REPO_ROOT", fake_repo)
    assert settings.effective_ui_dist is None

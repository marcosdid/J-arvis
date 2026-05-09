from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from orchestrator.main import create_app


@pytest.mark.integration
async def test_serves_index_html_at_root(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text(
        "<!doctype html><html><head><title>J-arvis</title></head></html>",
        encoding="utf-8",
    )

    app = create_app(ui_dist=tmp_path)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert "<title>J-arvis</title>" in response.text


@pytest.mark.integration
async def test_root_returns_404_when_no_ui_dist() -> None:
    app = create_app(ui_dist=None)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/")

    assert response.status_code == 404

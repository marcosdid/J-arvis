import pytest
from httpx import ASGITransport, AsyncClient

from orchestrator.main import create_app


@pytest.mark.integration
async def test_get_health_returns_ok() -> None:
    app = create_app(ui_dist=None)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

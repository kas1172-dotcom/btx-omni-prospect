import pytest
from httpx import ASGITransport, AsyncClient

from btx_omni.app import create_app


@pytest.mark.asyncio
async def test_health_endpoint() -> None:
    transport = ASGITransport(app=create_app())

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

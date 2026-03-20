"""
FastAPI smoke tests for public health endpoints.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from forest.api.app import create_app


@pytest.mark.asyncio
async def test_healthz() -> None:
    """``GET /healthz`` returns 200 without hitting the database."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

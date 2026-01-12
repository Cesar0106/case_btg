"""
Testes para o endpoint de healthcheck.
"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    """Cliente HTTP assíncrono para testes."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.anyio
async def test_health_check_returns_200(client: AsyncClient):
    """Verifica se o endpoint /health retorna status 200."""
    response = await client.get("/health")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_health_check_returns_healthy_status(client: AsyncClient):
    """Verifica se o endpoint /health retorna status 'healthy'."""
    response = await client.get("/health")
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.anyio
async def test_health_check_returns_app_info(client: AsyncClient):
    """Verifica se o endpoint /health retorna informações da aplicação."""
    response = await client.get("/health")
    data = response.json()
    assert "app_name" in data
    assert "environment" in data
    assert data["app_name"] == "Library API"

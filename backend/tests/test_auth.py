"""
Testes de integração para endpoints de autenticação.
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


class TestSignup:
    """Testes para POST /api/v1/auth/signup."""

    @pytest.mark.anyio
    async def test_signup_success(self, client: AsyncClient):
        """Signup com dados válidos deve retornar 201."""
        response = await client.post(
            "/api/v1/auth/signup",
            json={
                "name": "Test User",
                "email": "test@example.com",
                "password": "Test1234",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["name"] == "Test User"
        assert data["role"] == "USER"
        assert "id" in data
        assert "password" not in data
        assert "password_hash" not in data

    @pytest.mark.anyio
    async def test_signup_invalid_email(self, client: AsyncClient):
        """Email inválido deve retornar 422."""
        response = await client.post(
            "/api/v1/auth/signup",
            json={
                "name": "Test User",
                "email": "invalid-email",
                "password": "Test1234",
            },
        )

        assert response.status_code == 422

    @pytest.mark.anyio
    async def test_signup_weak_password(self, client: AsyncClient):
        """Senha fraca deve retornar 422."""
        response = await client.post(
            "/api/v1/auth/signup",
            json={
                "name": "Test User",
                "email": "test2@example.com",
                "password": "weak",
            },
        )

        assert response.status_code == 422


class TestLogin:
    """Testes para POST /api/v1/auth/login."""

    @pytest.mark.anyio
    async def test_login_invalid_credentials(self, client: AsyncClient):
        """Login com credenciais inválidas deve retornar 401."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "WrongPass1",
            },
        )

        assert response.status_code == 401


class TestMe:
    """Testes para GET /api/v1/auth/me."""

    @pytest.mark.anyio
    async def test_me_without_token(self, client: AsyncClient):
        """Acesso sem token deve retornar 403."""
        response = await client.get("/api/v1/auth/me")

        assert response.status_code == 403

    @pytest.mark.anyio
    async def test_me_with_invalid_token(self, client: AsyncClient):
        """Acesso com token inválido deve retornar 401."""
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid-token"},
        )

        assert response.status_code == 401

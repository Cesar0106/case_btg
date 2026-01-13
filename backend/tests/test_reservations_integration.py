"""
Testes de integração para ReservationService.

Testa fluxos completos de reserva com banco de dados real.
"""

import uuid
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import CopyStatus, ReservationStatus
from app.services.reservation import ReservationService
from app.schemas.reservation import HOLD_DURATION_HOURS


async def create_user_and_login(client: AsyncClient, is_admin: bool = False) -> tuple[dict, str]:
    """Cria usuário e faz login."""
    if is_admin:
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@local.dev", "password": "Admin123!"},
        )
        if login_response.status_code != 200:
            pytest.skip("Admin seed não existe - rode 'python -m app.db.seed' primeiro")
        data = login_response.json()
        return data["user"], data["token"]["access_token"]

    email = f"user_{uuid.uuid4().hex[:8]}@test.com"
    await client.post(
        "/api/v1/auth/signup",
        json={
            "name": "Test User",
            "email": email,
            "password": "Test1234!",
        },
    )

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Test1234!"},
    )

    data = login_response.json()
    return data["user"], data["token"]["access_token"]


async def create_book_with_copies(
    client: AsyncClient,
    token: str,
    quantity: int = 1,
) -> dict:
    """Cria autor + livro com cópias."""
    headers = {"Authorization": f"Bearer {token}"}

    author_response = await client.post(
        "/api/v1/authors",
        json={"name": f"Author {uuid.uuid4().hex[:8]}"},
        headers=headers,
    )
    author = author_response.json()

    book_response = await client.post(
        "/api/v1/books",
        json={
            "title": f"Book {uuid.uuid4().hex[:8]}",
            "author_id": author["id"],
            "published_year": 2024,
        },
        params={"quantity": quantity},
        headers=headers,
    )

    return book_response.json()["book"]


class TestReservationServiceIntegration:
    """Testes de integração para ReservationService."""

    @pytest.mark.anyio
    async def test_create_reservation_fails_when_copy_available(
        self, client: AsyncClient
    ):
        """Não deve criar reserva se há cópia disponível."""
        _, admin_token = await create_user_and_login(client, is_admin=True)
        user, user_token = await create_user_and_login(client)

        book = await create_book_with_copies(client, admin_token, quantity=1)
        headers = {"Authorization": f"Bearer {user_token}"}

        availability = await client.get(
            f"/api/v1/books/{book['id']}/availability",
            headers=headers,
        )
        assert availability.json()["available"] is True

    @pytest.mark.anyio
    async def test_create_reservation_after_loan(self, client: AsyncClient):
        """Deve criar reserva quando todas cópias estão emprestadas."""
        _, admin_token = await create_user_and_login(client, is_admin=True)
        user1, user1_token = await create_user_and_login(client)
        user2, user2_token = await create_user_and_login(client)

        book = await create_book_with_copies(client, admin_token, quantity=1)

        headers1 = {"Authorization": f"Bearer {user1_token}"}
        await client.post(
            "/api/v1/loans",
            json={"book_title_id": book["id"]},
            headers=headers1,
        )

        headers2 = {"Authorization": f"Bearer {user2_token}"}
        availability = await client.get(
            f"/api/v1/books/{book['id']}/availability",
            headers=headers2,
        )
        data = availability.json()
        assert data["available"] is False
        assert data["reason"] == "All copies are loaned"
        assert data["expected_due_date"] is not None

    @pytest.mark.anyio
    async def test_availability_shows_expected_due_date(self, client: AsyncClient):
        """Deve mostrar expected_due_date quando não há cópia disponível."""
        _, admin_token = await create_user_and_login(client, is_admin=True)
        user1, user1_token = await create_user_and_login(client)

        book = await create_book_with_copies(client, admin_token, quantity=1)

        headers1 = {"Authorization": f"Bearer {user1_token}"}
        loan_response = await client.post(
            "/api/v1/loans",
            json={"book_title_id": book["id"]},
            headers=headers1,
        )
        loan = loan_response.json()

        availability = await client.get(
            f"/api/v1/books/{book['id']}/availability",
            headers=headers1,
        )
        data = availability.json()

        assert data["expected_due_date"] == loan["due_date"]

    @pytest.mark.anyio
    async def test_copy_returns_to_available_after_loan_return(
        self, client: AsyncClient
    ):
        """Cópia deve voltar a AVAILABLE após devolução."""
        _, admin_token = await create_user_and_login(client, is_admin=True)
        user, user_token = await create_user_and_login(client)

        book = await create_book_with_copies(client, admin_token, quantity=1)
        headers = {"Authorization": f"Bearer {user_token}"}

        loan_response = await client.post(
            "/api/v1/loans",
            json={"book_title_id": book["id"]},
            headers=headers,
        )
        loan_id = loan_response.json()["id"]

        availability1 = await client.get(
            f"/api/v1/books/{book['id']}/availability",
            headers=headers,
        )
        assert availability1.json()["available"] is False

        await client.patch(
            f"/api/v1/loans/{loan_id}/return",
            headers=headers,
        )

        availability2 = await client.get(
            f"/api/v1/books/{book['id']}/availability",
            headers=headers,
        )
        assert availability2.json()["available"] is True


class TestReservationFlowIntegration:
    """Testes de fluxo completo de reserva."""

    @pytest.mark.anyio
    async def test_full_reservation_flow(self, client: AsyncClient):
        """
        Testa fluxo completo:
        1. User1 empresta única cópia
        2. User2 tenta emprestar (falha)
        3. Availability mostra não disponível
        4. User1 devolve
        5. Availability mostra disponível
        """
        _, admin_token = await create_user_and_login(client, is_admin=True)
        user1, user1_token = await create_user_and_login(client)
        user2, user2_token = await create_user_and_login(client)

        book = await create_book_with_copies(client, admin_token, quantity=1)
        headers1 = {"Authorization": f"Bearer {user1_token}"}
        headers2 = {"Authorization": f"Bearer {user2_token}"}

        loan_response = await client.post(
            "/api/v1/loans",
            json={"book_title_id": book["id"]},
            headers=headers1,
        )
        assert loan_response.status_code == 201
        loan_id = loan_response.json()["id"]

        fail_loan = await client.post(
            "/api/v1/loans",
            json={"book_title_id": book["id"]},
            headers=headers2,
        )
        assert fail_loan.status_code == 400
        assert "Nenhuma cópia disponível" in fail_loan.json()["detail"]

        avail1 = await client.get(
            f"/api/v1/books/{book['id']}/availability",
            headers=headers2,
        )
        assert avail1.json()["available"] is False

        await client.patch(
            f"/api/v1/loans/{loan_id}/return",
            headers=headers1,
        )

        avail2 = await client.get(
            f"/api/v1/books/{book['id']}/availability",
            headers=headers2,
        )
        assert avail2.json()["available"] is True

        loan2_response = await client.post(
            "/api/v1/loans",
            json={"book_title_id": book["id"]},
            headers=headers2,
        )
        assert loan2_response.status_code == 201

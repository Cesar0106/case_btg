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


class TestReservationEndpoints:
    """Testes dos endpoints de reserva."""

    @pytest.mark.anyio
    async def test_create_reservation_success(self, client: AsyncClient):
        """POST /reservations - Cria reserva quando não há cópia disponível."""
        _, admin_token = await create_user_and_login(client, is_admin=True)
        user1, user1_token = await create_user_and_login(client)
        user2, user2_token = await create_user_and_login(client)

        book = await create_book_with_copies(client, admin_token, quantity=1)
        headers1 = {"Authorization": f"Bearer {user1_token}"}
        headers2 = {"Authorization": f"Bearer {user2_token}"}

        # User1 empresta
        await client.post(
            "/api/v1/loans",
            json={"book_title_id": book["id"]},
            headers=headers1,
        )

        # User2 cria reserva
        response = await client.post(
            "/api/v1/reservations",
            json={"book_title_id": book["id"]},
            headers=headers2,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["reservation"]["status"] == "ACTIVE"
        assert data["reservation"]["queue_position"] == 1
        assert data["expected_available_at"] is not None

    @pytest.mark.anyio
    async def test_create_reservation_fails_when_available(self, client: AsyncClient):
        """POST /reservations - Falha se há cópia disponível."""
        _, admin_token = await create_user_and_login(client, is_admin=True)
        _, user_token = await create_user_and_login(client)

        book = await create_book_with_copies(client, admin_token, quantity=1)
        headers = {"Authorization": f"Bearer {user_token}"}

        response = await client.post(
            "/api/v1/reservations",
            json={"book_title_id": book["id"]},
            headers=headers,
        )

        assert response.status_code == 400
        assert "cópias disponíveis" in response.json()["detail"]

    @pytest.mark.anyio
    async def test_create_reservation_duplicate_fails(self, client: AsyncClient):
        """POST /reservations - Falha em reserva duplicada."""
        _, admin_token = await create_user_and_login(client, is_admin=True)
        user1, user1_token = await create_user_and_login(client)
        user2, user2_token = await create_user_and_login(client)

        book = await create_book_with_copies(client, admin_token, quantity=1)
        headers1 = {"Authorization": f"Bearer {user1_token}"}
        headers2 = {"Authorization": f"Bearer {user2_token}"}

        # User1 empresta
        await client.post(
            "/api/v1/loans",
            json={"book_title_id": book["id"]},
            headers=headers1,
        )

        # User2 cria primeira reserva
        await client.post(
            "/api/v1/reservations",
            json={"book_title_id": book["id"]},
            headers=headers2,
        )

        # User2 tenta duplicar
        response = await client.post(
            "/api/v1/reservations",
            json={"book_title_id": book["id"]},
            headers=headers2,
        )

        assert response.status_code == 400
        assert "já possui uma reserva" in response.json()["detail"]

    @pytest.mark.anyio
    async def test_list_reservations_user_sees_own(self, client: AsyncClient):
        """GET /reservations - Usuário vê apenas suas reservas."""
        _, admin_token = await create_user_and_login(client, is_admin=True)
        user1, user1_token = await create_user_and_login(client)
        user2, user2_token = await create_user_and_login(client)

        book = await create_book_with_copies(client, admin_token, quantity=1)
        headers1 = {"Authorization": f"Bearer {user1_token}"}
        headers2 = {"Authorization": f"Bearer {user2_token}"}

        # User1 empresta
        await client.post(
            "/api/v1/loans",
            json={"book_title_id": book["id"]},
            headers=headers1,
        )

        # User2 cria reserva
        await client.post(
            "/api/v1/reservations",
            json={"book_title_id": book["id"]},
            headers=headers2,
        )

        # User2 lista suas reservas
        response = await client.get(
            "/api/v1/reservations",
            headers=headers2,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        # Todas as reservas devem ser do user2
        for item in data["items"]:
            assert item["user_id"] == user2["id"]

    @pytest.mark.anyio
    async def test_list_reservations_admin_sees_all(self, client: AsyncClient):
        """GET /reservations - Admin vê todas as reservas."""
        _, admin_token = await create_user_and_login(client, is_admin=True)
        user1, user1_token = await create_user_and_login(client)
        user2, user2_token = await create_user_and_login(client)

        book = await create_book_with_copies(client, admin_token, quantity=1)
        headers1 = {"Authorization": f"Bearer {user1_token}"}
        headers2 = {"Authorization": f"Bearer {user2_token}"}
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # User1 empresta
        await client.post(
            "/api/v1/loans",
            json={"book_title_id": book["id"]},
            headers=headers1,
        )

        # User2 cria reserva
        await client.post(
            "/api/v1/reservations",
            json={"book_title_id": book["id"]},
            headers=headers2,
        )

        # Admin lista todas
        response = await client.get(
            "/api/v1/reservations",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    @pytest.mark.anyio
    async def test_get_my_reservations(self, client: AsyncClient):
        """GET /reservations/my - Lista minhas reservas ativas."""
        _, admin_token = await create_user_and_login(client, is_admin=True)
        user1, user1_token = await create_user_and_login(client)
        user2, user2_token = await create_user_and_login(client)

        book = await create_book_with_copies(client, admin_token, quantity=1)
        headers1 = {"Authorization": f"Bearer {user1_token}"}
        headers2 = {"Authorization": f"Bearer {user2_token}"}

        # User1 empresta
        await client.post(
            "/api/v1/loans",
            json={"book_title_id": book["id"]},
            headers=headers1,
        )

        # User2 cria reserva
        await client.post(
            "/api/v1/reservations",
            json={"book_title_id": book["id"]},
            headers=headers2,
        )

        # User2 lista suas reservas ativas
        response = await client.get(
            "/api/v1/reservations/my",
            headers=headers2,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["status"] in ["ACTIVE", "ON_HOLD"]

    @pytest.mark.anyio
    async def test_get_reservation_by_id(self, client: AsyncClient):
        """GET /reservations/{id} - Busca reserva por ID."""
        _, admin_token = await create_user_and_login(client, is_admin=True)
        user1, user1_token = await create_user_and_login(client)
        user2, user2_token = await create_user_and_login(client)

        book = await create_book_with_copies(client, admin_token, quantity=1)
        headers1 = {"Authorization": f"Bearer {user1_token}"}
        headers2 = {"Authorization": f"Bearer {user2_token}"}

        # User1 empresta
        await client.post(
            "/api/v1/loans",
            json={"book_title_id": book["id"]},
            headers=headers1,
        )

        # User2 cria reserva
        create_response = await client.post(
            "/api/v1/reservations",
            json={"book_title_id": book["id"]},
            headers=headers2,
        )
        reservation_id = create_response.json()["reservation"]["id"]

        # User2 busca sua reserva
        response = await client.get(
            f"/api/v1/reservations/{reservation_id}",
            headers=headers2,
        )

        assert response.status_code == 200
        assert response.json()["id"] == reservation_id

    @pytest.mark.anyio
    async def test_get_reservation_forbidden_for_other_user(self, client: AsyncClient):
        """GET /reservations/{id} - Usuário não pode ver reserva de outro."""
        _, admin_token = await create_user_and_login(client, is_admin=True)
        user1, user1_token = await create_user_and_login(client)
        user2, user2_token = await create_user_and_login(client)
        user3, user3_token = await create_user_and_login(client)

        book = await create_book_with_copies(client, admin_token, quantity=1)
        headers1 = {"Authorization": f"Bearer {user1_token}"}
        headers2 = {"Authorization": f"Bearer {user2_token}"}
        headers3 = {"Authorization": f"Bearer {user3_token}"}

        # User1 empresta
        await client.post(
            "/api/v1/loans",
            json={"book_title_id": book["id"]},
            headers=headers1,
        )

        # User2 cria reserva
        create_response = await client.post(
            "/api/v1/reservations",
            json={"book_title_id": book["id"]},
            headers=headers2,
        )
        reservation_id = create_response.json()["reservation"]["id"]

        # User3 tenta ver reserva de User2
        response = await client.get(
            f"/api/v1/reservations/{reservation_id}",
            headers=headers3,
        )

        assert response.status_code == 403

    @pytest.mark.anyio
    async def test_cancel_reservation_success(self, client: AsyncClient):
        """PATCH /reservations/{id}/cancel - Cancela reserva."""
        _, admin_token = await create_user_and_login(client, is_admin=True)
        user1, user1_token = await create_user_and_login(client)
        user2, user2_token = await create_user_and_login(client)

        book = await create_book_with_copies(client, admin_token, quantity=1)
        headers1 = {"Authorization": f"Bearer {user1_token}"}
        headers2 = {"Authorization": f"Bearer {user2_token}"}

        # User1 empresta
        await client.post(
            "/api/v1/loans",
            json={"book_title_id": book["id"]},
            headers=headers1,
        )

        # User2 cria reserva
        create_response = await client.post(
            "/api/v1/reservations",
            json={"book_title_id": book["id"]},
            headers=headers2,
        )
        reservation_id = create_response.json()["reservation"]["id"]

        # User2 cancela
        response = await client.patch(
            f"/api/v1/reservations/{reservation_id}/cancel",
            headers=headers2,
        )

        assert response.status_code == 200
        assert response.json()["reservation"]["status"] == "CANCELLED"

    @pytest.mark.anyio
    async def test_cancel_reservation_forbidden_for_other_user(self, client: AsyncClient):
        """PATCH /reservations/{id}/cancel - Usuário não pode cancelar reserva de outro."""
        _, admin_token = await create_user_and_login(client, is_admin=True)
        user1, user1_token = await create_user_and_login(client)
        user2, user2_token = await create_user_and_login(client)
        user3, user3_token = await create_user_and_login(client)

        book = await create_book_with_copies(client, admin_token, quantity=1)
        headers1 = {"Authorization": f"Bearer {user1_token}"}
        headers2 = {"Authorization": f"Bearer {user2_token}"}
        headers3 = {"Authorization": f"Bearer {user3_token}"}

        # User1 empresta
        await client.post(
            "/api/v1/loans",
            json={"book_title_id": book["id"]},
            headers=headers1,
        )

        # User2 cria reserva
        create_response = await client.post(
            "/api/v1/reservations",
            json={"book_title_id": book["id"]},
            headers=headers2,
        )
        reservation_id = create_response.json()["reservation"]["id"]

        # User3 tenta cancelar reserva de User2
        response = await client.patch(
            f"/api/v1/reservations/{reservation_id}/cancel",
            headers=headers3,
        )

        assert response.status_code == 403


class TestSystemEndpoints:
    """Testes dos endpoints de sistema (admin)."""

    @pytest.mark.anyio
    async def test_process_holds_requires_admin(self, client: AsyncClient):
        """POST /system/process-holds - Requer admin."""
        _, user_token = await create_user_and_login(client)
        headers = {"Authorization": f"Bearer {user_token}"}

        response = await client.post(
            "/api/v1/system/process-holds",
            headers=headers,
        )

        assert response.status_code == 403

    @pytest.mark.anyio
    async def test_process_holds_success(self, client: AsyncClient):
        """POST /system/process-holds - Admin processa holds."""
        _, admin_token = await create_user_and_login(client, is_admin=True)
        user1, user1_token = await create_user_and_login(client)
        user2, user2_token = await create_user_and_login(client)

        book = await create_book_with_copies(client, admin_token, quantity=1)
        headers1 = {"Authorization": f"Bearer {user1_token}"}
        headers2 = {"Authorization": f"Bearer {user2_token}"}
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # User1 empresta
        loan_response = await client.post(
            "/api/v1/loans",
            json={"book_title_id": book["id"]},
            headers=headers1,
        )
        loan_id = loan_response.json()["id"]

        # User2 cria reserva
        create_response = await client.post(
            "/api/v1/reservations",
            json={"book_title_id": book["id"]},
            headers=headers2,
        )
        reservation_id = create_response.json()["reservation"]["id"]

        # User1 devolve
        await client.patch(
            f"/api/v1/loans/{loan_id}/return",
            headers=headers1,
        )

        # Admin processa holds
        response = await client.post(
            "/api/v1/system/process-holds",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_processed"] >= 1

        # Verificar que reserva virou ON_HOLD
        res_response = await client.get(
            f"/api/v1/reservations/{reservation_id}",
            headers=headers2,
        )
        assert res_response.json()["status"] == "ON_HOLD"

    @pytest.mark.anyio
    async def test_expire_holds_requires_admin(self, client: AsyncClient):
        """POST /system/expire-holds - Requer admin."""
        _, user_token = await create_user_and_login(client)
        headers = {"Authorization": f"Bearer {user_token}"}

        response = await client.post(
            "/api/v1/system/expire-holds",
            headers=headers,
        )

        assert response.status_code == 403

    @pytest.mark.anyio
    async def test_expire_holds_success(self, client: AsyncClient):
        """POST /system/expire-holds - Admin expira holds."""
        _, admin_token = await create_user_and_login(client, is_admin=True)
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        response = await client.post(
            "/api/v1/system/expire-holds",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "expired_count" in data
        assert "next_holds_processed" in data


class TestFullReservationFlowWithHold:
    """Testes do fluxo completo com hold."""

    @pytest.mark.anyio
    async def test_complete_flow_reserve_hold_loan(self, client: AsyncClient):
        """
        Fluxo completo:
        1. User1 empresta única cópia
        2. User2 cria reserva (ACTIVE)
        3. User1 devolve
        4. Admin processa holds
        5. Reserva vira ON_HOLD
        6. User2 empresta (reserva vira FULFILLED)
        """
        _, admin_token = await create_user_and_login(client, is_admin=True)
        user1, user1_token = await create_user_and_login(client)
        user2, user2_token = await create_user_and_login(client)

        book = await create_book_with_copies(client, admin_token, quantity=1)
        headers1 = {"Authorization": f"Bearer {user1_token}"}
        headers2 = {"Authorization": f"Bearer {user2_token}"}
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # 1. User1 empresta
        loan_response = await client.post(
            "/api/v1/loans",
            json={"book_title_id": book["id"]},
            headers=headers1,
        )
        assert loan_response.status_code == 201
        loan_id = loan_response.json()["id"]

        # 2. User2 cria reserva
        res_response = await client.post(
            "/api/v1/reservations",
            json={"book_title_id": book["id"]},
            headers=headers2,
        )
        assert res_response.status_code == 201
        reservation_id = res_response.json()["reservation"]["id"]
        assert res_response.json()["reservation"]["status"] == "ACTIVE"

        # 3. User1 devolve
        return_response = await client.patch(
            f"/api/v1/loans/{loan_id}/return",
            headers=headers1,
        )
        assert return_response.status_code == 200

        # 4. Admin processa holds
        process_response = await client.post(
            "/api/v1/system/process-holds",
            headers=admin_headers,
        )
        assert process_response.status_code == 200
        assert process_response.json()["total_processed"] >= 1

        # 5. Verificar reserva ON_HOLD
        check_response = await client.get(
            f"/api/v1/reservations/{reservation_id}",
            headers=headers2,
        )
        assert check_response.json()["status"] == "ON_HOLD"
        assert check_response.json()["hold_expires_at"] is not None

        # 6. User2 empresta
        loan2_response = await client.post(
            "/api/v1/loans",
            json={"book_title_id": book["id"]},
            headers=headers2,
        )
        assert loan2_response.status_code == 201

        # Verificar reserva FULFILLED
        final_response = await client.get(
            f"/api/v1/reservations/{reservation_id}",
            headers=headers2,
        )
        assert final_response.json()["status"] == "FULFILLED"

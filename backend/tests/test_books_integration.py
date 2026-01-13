"""
Testes de integração para endpoints de Books.

Testa:
    - Verificar disponibilidade de um título
"""

import uuid

import pytest
from httpx import AsyncClient


# ==========================================
# Helper functions
# ==========================================

async def create_user_and_login(client: AsyncClient, is_admin: bool = False) -> tuple[dict, str]:
    """
    Cria usuário e faz login.

    Args:
        client: Cliente HTTP
        is_admin: Se True, usa admin@local.dev (precisa existir via seed)

    Returns:
        Tupla (dados do usuário, access_token)
    """
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
    """
    Cria autor + livro com cópias.

    Returns:
        Dados do livro criado
    """
    headers = {"Authorization": f"Bearer {token}"}

    # Criar autor
    author_response = await client.post(
        "/api/v1/authors",
        json={"name": f"Author {uuid.uuid4().hex[:8]}"},
        headers=headers,
    )
    author = author_response.json()

    # Criar livro com cópias
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


# ==========================================
# Test: Book Availability
# ==========================================

class TestBookAvailability:
    """Testes para GET /books/{book_id}/availability."""

    @pytest.mark.anyio
    async def test_availability_with_available_copies(self, client: AsyncClient):
        """Livro com cópias disponíveis deve retornar available=True."""
        _, admin_token = await create_user_and_login(client, is_admin=True)
        _, user_token = await create_user_and_login(client)

        # Criar livro com 2 cópias
        book = await create_book_with_copies(client, admin_token, quantity=2)
        headers = {"Authorization": f"Bearer {user_token}"}

        # Verificar disponibilidade
        response = await client.get(
            f"/api/v1/books/{book['id']}/availability",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["book_title_id"] == book["id"]
        assert data["available"] is True
        assert data["reason"] is None
        assert data["expected_due_date"] is None
        assert data["available_copies"] == 2
        assert data["total_copies"] == 2

    @pytest.mark.anyio
    async def test_availability_all_copies_loaned(self, client: AsyncClient):
        """Livro com todas cópias emprestadas deve retornar reason correta."""
        _, admin_token = await create_user_and_login(client, is_admin=True)
        _, user_token = await create_user_and_login(client)

        # Criar livro com 1 cópia
        book = await create_book_with_copies(client, admin_token, quantity=1)
        headers = {"Authorization": f"Bearer {user_token}"}

        # Fazer empréstimo
        await client.post(
            "/api/v1/loans",
            json={"book_title_id": book["id"]},
            headers=headers,
        )

        # Verificar disponibilidade
        response = await client.get(
            f"/api/v1/books/{book['id']}/availability",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["available"] is False
        assert data["reason"] == "All copies are loaned"
        assert data["expected_due_date"] is not None
        assert data["available_copies"] == 0
        assert data["total_copies"] == 1

    @pytest.mark.anyio
    async def test_availability_partial_loaned(self, client: AsyncClient):
        """Livro com algumas cópias emprestadas deve retornar available=True."""
        _, admin_token = await create_user_and_login(client, is_admin=True)
        _, user_token = await create_user_and_login(client)

        # Criar livro com 3 cópias
        book = await create_book_with_copies(client, admin_token, quantity=3)
        headers = {"Authorization": f"Bearer {user_token}"}

        # Fazer 1 empréstimo
        await client.post(
            "/api/v1/loans",
            json={"book_title_id": book["id"]},
            headers=headers,
        )

        # Verificar disponibilidade
        response = await client.get(
            f"/api/v1/books/{book['id']}/availability",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["available"] is True
        assert data["reason"] is None
        assert data["available_copies"] == 2
        assert data["total_copies"] == 3

    @pytest.mark.anyio
    async def test_availability_book_not_found(self, client: AsyncClient):
        """Buscar disponibilidade de livro inexistente deve retornar 404."""
        _, user_token = await create_user_and_login(client)
        headers = {"Authorization": f"Bearer {user_token}"}

        response = await client.get(
            f"/api/v1/books/{uuid.uuid4()}/availability",
            headers=headers,
        )

        assert response.status_code == 404
        assert "Livro não encontrado" in response.json()["detail"]

    @pytest.mark.anyio
    async def test_availability_without_auth(self, client: AsyncClient):
        """Buscar disponibilidade sem autenticação deve falhar."""
        response = await client.get(
            f"/api/v1/books/{uuid.uuid4()}/availability",
        )

        assert response.status_code == 401

    @pytest.mark.anyio
    async def test_availability_expected_due_date(self, client: AsyncClient):
        """expected_due_date deve ser a menor due_date dos empréstimos ativos."""
        _, admin_token = await create_user_and_login(client, is_admin=True)
        user1, user1_token = await create_user_and_login(client)
        user2, user2_token = await create_user_and_login(client)

        # Criar livro com 2 cópias
        book = await create_book_with_copies(client, admin_token, quantity=2)

        # User1 faz empréstimo
        headers1 = {"Authorization": f"Bearer {user1_token}"}
        loan1_response = await client.post(
            "/api/v1/loans",
            json={"book_title_id": book["id"]},
            headers=headers1,
        )
        loan1 = loan1_response.json()

        # User2 faz empréstimo
        headers2 = {"Authorization": f"Bearer {user2_token}"}
        loan2_response = await client.post(
            "/api/v1/loans",
            json={"book_title_id": book["id"]},
            headers=headers2,
        )

        # Verificar disponibilidade (todas emprestadas)
        response = await client.get(
            f"/api/v1/books/{book['id']}/availability",
            headers=headers1,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["available"] is False
        # expected_due_date deve ser a menor (primeira criada, que é loan1)
        assert data["expected_due_date"] is not None
        # A due_date mais antiga é a do primeiro empréstimo
        assert data["expected_due_date"] == loan1["due_date"]

    @pytest.mark.anyio
    async def test_availability_after_return(self, client: AsyncClient):
        """Após devolução, disponibilidade deve voltar a True."""
        _, admin_token = await create_user_and_login(client, is_admin=True)
        _, user_token = await create_user_and_login(client)

        # Criar livro com 1 cópia
        book = await create_book_with_copies(client, admin_token, quantity=1)
        headers = {"Authorization": f"Bearer {user_token}"}

        # Fazer empréstimo
        loan_response = await client.post(
            "/api/v1/loans",
            json={"book_title_id": book["id"]},
            headers=headers,
        )
        loan_id = loan_response.json()["id"]

        # Verificar que está indisponível
        response1 = await client.get(
            f"/api/v1/books/{book['id']}/availability",
            headers=headers,
        )
        assert response1.json()["available"] is False

        # Devolver
        await client.patch(
            f"/api/v1/loans/{loan_id}/return",
            headers=headers,
        )

        # Verificar que voltou a estar disponível
        response2 = await client.get(
            f"/api/v1/books/{book['id']}/availability",
            headers=headers,
        )

        assert response2.status_code == 200
        data = response2.json()
        assert data["available"] is True
        assert data["reason"] is None
        assert data["expected_due_date"] is None
        assert data["available_copies"] == 1

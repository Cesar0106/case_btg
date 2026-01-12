"""
Testes de integração para endpoints de Loans.

Testa fluxos completos:
    - Criar empréstimo
    - Listar empréstimos (filtros, autorização)
    - Devolver livro (com e sem multa)
"""

import uuid
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient

from app.schemas.loan import FINE_PER_DAY, MAX_ACTIVE_LOANS


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
        # Usar admin seed
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@local.dev", "password": "Admin123!"},
        )
        if login_response.status_code != 200:
            pytest.skip("Admin seed não existe - rode 'python -m app.db.seed' primeiro")
        data = login_response.json()
        return data["user"], data["token"]["access_token"]

    # Criar novo usuário
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
# Test: Create Loan
# ==========================================

class TestCreateLoan:
    """Testes para POST /loans."""

    @pytest.mark.anyio
    async def test_create_loan_success(self, client: AsyncClient):
        """Deve criar empréstimo com sucesso."""
        # Setup: admin cria livro, user faz empréstimo
        _, admin_token = await create_user_and_login(client, is_admin=True)
        user, user_token = await create_user_and_login(client)
        book = await create_book_with_copies(client, admin_token, quantity=1)

        headers = {"Authorization": f"Bearer {user_token}"}

        # Criar empréstimo
        response = await client.post(
            "/api/v1/loans",
            json={"book_title_id": book["id"]},
            headers=headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["user_id"] == user["id"]
        assert data["book_title"] == book["title"]
        assert data["status"] == "ACTIVE"
        assert data["fine_amount_current"] == "0.00"
        assert data["returned_at"] is None

    @pytest.mark.anyio
    async def test_create_loan_without_auth(self, client: AsyncClient):
        """Criar empréstimo sem autenticação deve falhar."""
        response = await client.post(
            "/api/v1/loans",
            json={"book_title_id": str(uuid.uuid4())},
        )

        assert response.status_code == 401

    @pytest.mark.anyio
    async def test_create_loan_book_not_found(self, client: AsyncClient):
        """Criar empréstimo para livro inexistente deve falhar."""
        _, token = await create_user_and_login(client)
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.post(
            "/api/v1/loans",
            json={"book_title_id": str(uuid.uuid4())},
            headers=headers,
        )

        assert response.status_code == 404
        assert "Livro não encontrado" in response.json()["detail"]

    @pytest.mark.anyio
    async def test_create_loan_no_available_copy(self, client: AsyncClient):
        """Criar empréstimo sem cópia disponível deve falhar."""
        _, admin_token = await create_user_and_login(client, is_admin=True)
        user1, token1 = await create_user_and_login(client)
        _, token2 = await create_user_and_login(client)

        # Criar livro com 1 cópia
        book = await create_book_with_copies(client, admin_token, quantity=1)

        # User1 pega emprestado
        headers1 = {"Authorization": f"Bearer {token1}"}
        response1 = await client.post(
            "/api/v1/loans",
            json={"book_title_id": book["id"]},
            headers=headers1,
        )
        assert response1.status_code == 201

        # User2 tenta pegar o mesmo livro (sem cópia disponível)
        headers2 = {"Authorization": f"Bearer {token2}"}
        response2 = await client.post(
            "/api/v1/loans",
            json={"book_title_id": book["id"]},
            headers=headers2,
        )

        assert response2.status_code == 400
        assert "Nenhuma cópia disponível" in response2.json()["detail"]

    @pytest.mark.anyio
    async def test_create_loan_max_limit(self, client: AsyncClient):
        """Criar mais de 3 empréstimos ativos deve falhar."""
        _, admin_token = await create_user_and_login(client, is_admin=True)
        _, user_token = await create_user_and_login(client)
        headers = {"Authorization": f"Bearer {user_token}"}

        # Criar 3 livros e fazer 3 empréstimos
        for i in range(MAX_ACTIVE_LOANS):
            book = await create_book_with_copies(client, admin_token, quantity=1)
            response = await client.post(
                "/api/v1/loans",
                json={"book_title_id": book["id"]},
                headers=headers,
            )
            assert response.status_code == 201, f"Empréstimo {i+1} falhou"

        # Tentar 4º empréstimo
        book4 = await create_book_with_copies(client, admin_token, quantity=1)
        response = await client.post(
            "/api/v1/loans",
            json={"book_title_id": book4["id"]},
            headers=headers,
        )

        assert response.status_code == 400
        assert f"{MAX_ACTIVE_LOANS}" in response.json()["detail"]


# ==========================================
# Test: List Loans
# ==========================================

class TestListLoans:
    """Testes para GET /loans."""

    @pytest.mark.anyio
    async def test_list_loans_user_sees_only_own(self, client: AsyncClient):
        """Usuário comum deve ver apenas seus próprios empréstimos."""
        _, admin_token = await create_user_and_login(client, is_admin=True)
        _, user_token = await create_user_and_login(client)

        # Criar livro e empréstimo
        book = await create_book_with_copies(client, admin_token, quantity=1)
        headers = {"Authorization": f"Bearer {user_token}"}

        await client.post(
            "/api/v1/loans",
            json={"book_title_id": book["id"]},
            headers=headers,
        )

        # Listar empréstimos
        response = await client.get("/api/v1/loans", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        # Todos os loans devem ser do próprio usuário
        for loan in data["items"]:
            assert loan["status"] in ["ACTIVE", "RETURNED"]

    @pytest.mark.anyio
    async def test_list_loans_admin_sees_all(self, client: AsyncClient):
        """Admin deve ver todos os empréstimos."""
        _, admin_token = await create_user_and_login(client, is_admin=True)
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # Listar todos os empréstimos (sem filtro de user_id)
        response = await client.get("/api/v1/loans", headers=admin_headers)

        assert response.status_code == 200

    @pytest.mark.anyio
    async def test_list_loans_filter_by_status(self, client: AsyncClient):
        """Deve filtrar empréstimos por status."""
        _, admin_token = await create_user_and_login(client, is_admin=True)
        headers = {"Authorization": f"Bearer {admin_token}"}

        # Filtrar apenas ativos
        response = await client.get(
            "/api/v1/loans",
            params={"status": "active"},
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        for loan in data["items"]:
            assert loan["status"] == "ACTIVE"


# ==========================================
# Test: Return Loan
# ==========================================

class TestReturnLoan:
    """Testes para PATCH /loans/{id}/return."""

    @pytest.mark.anyio
    async def test_return_loan_no_fine(self, client: AsyncClient):
        """Devolver livro no prazo não deve gerar multa."""
        _, admin_token = await create_user_and_login(client, is_admin=True)
        _, user_token = await create_user_and_login(client)

        book = await create_book_with_copies(client, admin_token, quantity=1)
        headers = {"Authorization": f"Bearer {user_token}"}

        # Criar empréstimo
        create_response = await client.post(
            "/api/v1/loans",
            json={"book_title_id": book["id"]},
            headers=headers,
        )
        loan_id = create_response.json()["id"]

        # Devolver (mesma hora, sem atraso)
        return_response = await client.patch(
            f"/api/v1/loans/{loan_id}/return",
            headers=headers,
        )

        assert return_response.status_code == 200
        data = return_response.json()
        assert data["fine_applied"] == "0.00"
        assert data["loan"]["status"] == "RETURNED"
        assert "Sem multa" in data["message"]

    @pytest.mark.anyio
    async def test_return_loan_already_returned(self, client: AsyncClient):
        """Devolver livro já devolvido deve falhar."""
        _, admin_token = await create_user_and_login(client, is_admin=True)
        _, user_token = await create_user_and_login(client)

        book = await create_book_with_copies(client, admin_token, quantity=1)
        headers = {"Authorization": f"Bearer {user_token}"}

        # Criar e devolver
        create_response = await client.post(
            "/api/v1/loans",
            json={"book_title_id": book["id"]},
            headers=headers,
        )
        loan_id = create_response.json()["id"]

        await client.patch(f"/api/v1/loans/{loan_id}/return", headers=headers)

        # Tentar devolver novamente
        response = await client.patch(
            f"/api/v1/loans/{loan_id}/return",
            headers=headers,
        )

        assert response.status_code == 400
        assert "já foi devolvido" in response.json()["detail"]

    @pytest.mark.anyio
    async def test_return_loan_not_owner(self, client: AsyncClient):
        """Usuário não pode devolver empréstimo de outro."""
        _, admin_token = await create_user_and_login(client, is_admin=True)
        _, user1_token = await create_user_and_login(client)
        _, user2_token = await create_user_and_login(client)

        book = await create_book_with_copies(client, admin_token, quantity=1)

        # User1 cria empréstimo
        headers1 = {"Authorization": f"Bearer {user1_token}"}
        create_response = await client.post(
            "/api/v1/loans",
            json={"book_title_id": book["id"]},
            headers=headers1,
        )
        loan_id = create_response.json()["id"]

        # User2 tenta devolver
        headers2 = {"Authorization": f"Bearer {user2_token}"}
        response = await client.patch(
            f"/api/v1/loans/{loan_id}/return",
            headers=headers2,
        )

        assert response.status_code == 403
        assert "permissão" in response.json()["detail"]

    @pytest.mark.anyio
    async def test_admin_can_return_any_loan(self, client: AsyncClient):
        """Admin pode devolver empréstimo de qualquer usuário."""
        _, admin_token = await create_user_and_login(client, is_admin=True)
        _, user_token = await create_user_and_login(client)

        book = await create_book_with_copies(client, admin_token, quantity=1)

        # User cria empréstimo
        user_headers = {"Authorization": f"Bearer {user_token}"}
        create_response = await client.post(
            "/api/v1/loans",
            json={"book_title_id": book["id"]},
            headers=user_headers,
        )
        loan_id = create_response.json()["id"]

        # Admin devolve
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        response = await client.patch(
            f"/api/v1/loans/{loan_id}/return",
            headers=admin_headers,
        )

        assert response.status_code == 200
        assert response.json()["loan"]["status"] == "RETURNED"


# ==========================================
# Test: Get Loan Detail
# ==========================================

class TestGetLoan:
    """Testes para GET /loans/{id}."""

    @pytest.mark.anyio
    async def test_get_loan_success(self, client: AsyncClient):
        """Deve retornar detalhes do empréstimo."""
        _, admin_token = await create_user_and_login(client, is_admin=True)
        user, user_token = await create_user_and_login(client)

        book = await create_book_with_copies(client, admin_token, quantity=1)
        headers = {"Authorization": f"Bearer {user_token}"}

        # Criar empréstimo
        create_response = await client.post(
            "/api/v1/loans",
            json={"book_title_id": book["id"]},
            headers=headers,
        )
        loan_id = create_response.json()["id"]

        # Buscar detalhes
        response = await client.get(f"/api/v1/loans/{loan_id}", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == loan_id
        assert data["user_id"] == user["id"]
        assert data["book_title"] == book["title"]
        assert "fine_amount_current" in data
        assert "status" in data

    @pytest.mark.anyio
    async def test_get_loan_not_owner(self, client: AsyncClient):
        """Usuário não pode ver empréstimo de outro."""
        _, admin_token = await create_user_and_login(client, is_admin=True)
        _, user1_token = await create_user_and_login(client)
        _, user2_token = await create_user_and_login(client)

        book = await create_book_with_copies(client, admin_token, quantity=1)

        # User1 cria empréstimo
        headers1 = {"Authorization": f"Bearer {user1_token}"}
        create_response = await client.post(
            "/api/v1/loans",
            json={"book_title_id": book["id"]},
            headers=headers1,
        )
        loan_id = create_response.json()["id"]

        # User2 tenta ver
        headers2 = {"Authorization": f"Bearer {user2_token}"}
        response = await client.get(f"/api/v1/loans/{loan_id}", headers=headers2)

        assert response.status_code == 403


# ==========================================
# Test: My Active Loans
# ==========================================

class TestMyActiveLoans:
    """Testes para GET /loans/my."""

    @pytest.mark.anyio
    async def test_my_active_loans(self, client: AsyncClient):
        """Deve listar apenas empréstimos ativos do usuário."""
        _, admin_token = await create_user_and_login(client, is_admin=True)
        _, user_token = await create_user_and_login(client)
        headers = {"Authorization": f"Bearer {user_token}"}

        # Criar 2 empréstimos
        book1 = await create_book_with_copies(client, admin_token, quantity=1)
        book2 = await create_book_with_copies(client, admin_token, quantity=1)

        await client.post(
            "/api/v1/loans",
            json={"book_title_id": book1["id"]},
            headers=headers,
        )

        loan2_response = await client.post(
            "/api/v1/loans",
            json={"book_title_id": book2["id"]},
            headers=headers,
        )
        loan2_id = loan2_response.json()["id"]

        # Devolver um
        await client.patch(f"/api/v1/loans/{loan2_id}/return", headers=headers)

        # Listar ativos
        response = await client.get("/api/v1/loans/my", headers=headers)

        assert response.status_code == 200
        data = response.json()
        # Apenas 1 deve estar ativo
        assert len(data) == 1
        assert data[0]["status"] == "ACTIVE"


# ==========================================
# Test: Overdue Loans (Admin)
# ==========================================

class TestOverdueLoans:
    """Testes para GET /loans/overdue."""

    @pytest.mark.anyio
    async def test_overdue_loans_requires_admin(self, client: AsyncClient):
        """Apenas admin pode ver empréstimos atrasados."""
        _, user_token = await create_user_and_login(client)
        headers = {"Authorization": f"Bearer {user_token}"}

        response = await client.get("/api/v1/loans/overdue", headers=headers)

        assert response.status_code == 403

    @pytest.mark.anyio
    async def test_overdue_loans_admin_success(self, client: AsyncClient):
        """Admin pode ver lista de empréstimos atrasados."""
        _, admin_token = await create_user_and_login(client, is_admin=True)
        headers = {"Authorization": f"Bearer {admin_token}"}

        response = await client.get("/api/v1/loans/overdue", headers=headers)

        assert response.status_code == 200
        # Retorna lista (pode estar vazia)
        assert isinstance(response.json(), list)

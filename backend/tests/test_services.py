"""
Testes unitários para services (mockando session).
"""

import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.user import User
from app.models.author import Author
from app.models.book import BookTitle, BookCopy
from app.models.loan import Loan
from app.models.enums import UserRole, CopyStatus
from app.schemas.user import UserCreate, UserUpdate
from app.schemas.author import AuthorCreate, AuthorUpdate
from app.schemas.book import BookTitleCreate
from app.schemas.loan import LOAN_PERIOD_DAYS, FINE_PER_DAY, MAX_ACTIVE_LOANS
from app.services.user import UserService
from app.services.author import AuthorService
from app.services.book import BookService
from app.services.loan import LoanService


# ==========================================
# Fixtures
# ==========================================

@pytest.fixture
def mock_db():
    """Mock da sessão do banco."""
    return AsyncMock()


@pytest.fixture
def sample_user():
    """Usuário de exemplo."""
    return User(
        id=uuid.uuid4(),
        name="Test User",
        email="test@example.com",
        password_hash="hashed_password",
        role=UserRole.USER,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_author():
    """Autor de exemplo."""
    author = Author(
        id=uuid.uuid4(),
        name="Test Author",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    author.books = []
    return author


@pytest.fixture
def sample_book(sample_author):
    """Livro de exemplo."""
    book = BookTitle(
        id=uuid.uuid4(),
        title="Test Book",
        author_id=sample_author.id,
        published_year=2020,
        pages=200,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    book.author = sample_author
    book.copies = []
    return book


# ==========================================
# UserService Tests
# ==========================================

class TestUserService:
    """Testes para UserService."""

    @pytest.mark.anyio
    async def test_get_by_id_success(self, mock_db, sample_user):
        """Deve retornar usuário quando encontrado."""
        service = UserService(mock_db)

        with patch.object(service.repo, 'get_by_id', return_value=sample_user):
            result = await service.get_by_id(sample_user.id)

        assert result.id == sample_user.id
        assert result.email == sample_user.email

    @pytest.mark.anyio
    async def test_get_by_id_not_found(self, mock_db):
        """Deve levantar 404 quando usuário não encontrado."""
        service = UserService(mock_db)

        with patch.object(service.repo, 'get_by_id', return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await service.get_by_id(uuid.uuid4())

        assert exc_info.value.status_code == 404
        assert "não encontrado" in exc_info.value.detail

    @pytest.mark.anyio
    async def test_create_success(self, mock_db, sample_user):
        """Deve criar usuário com sucesso."""
        service = UserService(mock_db)
        data = UserCreate(name="New User", email="new@example.com", password="Test1234")

        with patch.object(service.repo, 'email_exists', return_value=False):
            with patch.object(service.repo, 'create_user', return_value=sample_user):
                result = await service.create(data)

        assert result is not None

    @pytest.mark.anyio
    async def test_create_email_exists(self, mock_db):
        """Deve levantar 400 quando email já existe."""
        service = UserService(mock_db)
        data = UserCreate(name="New User", email="existing@example.com", password="Test1234")

        with patch.object(service.repo, 'email_exists', return_value=True):
            with pytest.raises(HTTPException) as exc_info:
                await service.create(data)

        assert exc_info.value.status_code == 400
        assert "já cadastrado" in exc_info.value.detail


# ==========================================
# AuthorService Tests
# ==========================================

class TestAuthorService:
    """Testes para AuthorService."""

    @pytest.mark.anyio
    async def test_get_by_id_success(self, mock_db, sample_author):
        """Deve retornar autor quando encontrado."""
        service = AuthorService(mock_db)

        with patch.object(service.repo, 'get_by_id', return_value=sample_author):
            result = await service.get_by_id(sample_author.id)

        assert result.id == sample_author.id
        assert result.name == sample_author.name

    @pytest.mark.anyio
    async def test_get_by_id_not_found(self, mock_db):
        """Deve levantar 404 quando autor não encontrado."""
        service = AuthorService(mock_db)

        with patch.object(service.repo, 'get_by_id', return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await service.get_by_id(uuid.uuid4())

        assert exc_info.value.status_code == 404

    @pytest.mark.anyio
    async def test_create_success(self, mock_db, sample_author):
        """Deve criar autor com sucesso."""
        service = AuthorService(mock_db)
        data = AuthorCreate(name="New Author")

        with patch.object(service.repo, 'create', return_value=sample_author):
            result = await service.create(data)

        assert result is not None

    @pytest.mark.anyio
    async def test_delete_with_books_fails(self, mock_db, sample_author, sample_book):
        """Deve falhar ao deletar autor com livros."""
        service = AuthorService(mock_db)
        sample_author.books = [sample_book]

        with patch.object(service.repo, 'get_with_books', return_value=sample_author):
            with pytest.raises(HTTPException) as exc_info:
                await service.delete(sample_author.id)

        assert exc_info.value.status_code == 400
        assert "livros cadastrados" in exc_info.value.detail


# ==========================================
# BookService Tests
# ==========================================

class TestBookService:
    """Testes para BookService."""

    @pytest.mark.anyio
    async def test_get_title_by_id_success(self, mock_db, sample_book):
        """Deve retornar livro quando encontrado."""
        service = BookService(mock_db)

        with patch.object(service.title_repo, 'get_with_author', return_value=sample_book):
            result = await service.get_title_by_id(sample_book.id)

        assert result.id == sample_book.id
        assert result.title == sample_book.title

    @pytest.mark.anyio
    async def test_get_title_by_id_not_found(self, mock_db):
        """Deve levantar 404 quando livro não encontrado."""
        service = BookService(mock_db)

        with patch.object(service.title_repo, 'get_with_author', return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await service.get_title_by_id(uuid.uuid4())

        assert exc_info.value.status_code == 404

    @pytest.mark.anyio
    async def test_create_title_with_copies_success(self, mock_db, sample_author, sample_book):
        """Deve criar título com cópias."""
        service = BookService(mock_db)
        data = BookTitleCreate(
            title="New Book",
            author_id=sample_author.id,
            published_year=2024,
            pages=300,
        )

        copies = [
            BookCopy(
                id=uuid.uuid4(),
                book_title_id=sample_book.id,
                status=CopyStatus.AVAILABLE,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            for _ in range(3)
        ]

        with patch.object(service.author_repo, 'get_by_id', return_value=sample_author):
            with patch.object(service.title_repo, 'create', return_value=sample_book):
                with patch.object(service.copy_repo, 'create_copies', return_value=copies):
                    with patch.object(service.title_repo, 'get_with_author', return_value=sample_book):
                        book, created_copies = await service.create_title_with_copies(data, quantity=3)

        assert book is not None
        assert len(created_copies) == 3

    @pytest.mark.anyio
    async def test_create_title_author_not_found(self, mock_db):
        """Deve falhar quando autor não existe."""
        service = BookService(mock_db)
        data = BookTitleCreate(
            title="New Book",
            author_id=uuid.uuid4(),
        )

        with patch.object(service.author_repo, 'get_by_id', return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await service.create_title_with_copies(data)

        assert exc_info.value.status_code == 404
        assert "Autor" in exc_info.value.detail

    @pytest.mark.anyio
    async def test_create_title_invalid_quantity(self, mock_db):
        """Deve falhar com quantidade inválida."""
        service = BookService(mock_db)
        data = BookTitleCreate(
            title="New Book",
            author_id=uuid.uuid4(),
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.create_title_with_copies(data, quantity=0)

        assert exc_info.value.status_code == 400
        assert "Quantidade" in exc_info.value.detail

    @pytest.mark.anyio
    async def test_delete_title_with_loaned_copies_fails(self, mock_db, sample_book):
        """Deve falhar ao deletar livro com cópias emprestadas."""
        service = BookService(mock_db)
        sample_book.copies = [
            BookCopy(
                id=uuid.uuid4(),
                book_title_id=sample_book.id,
                status=CopyStatus.LOANED,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        ]

        with patch.object(service.title_repo, 'get_with_copies', return_value=sample_book):
            with pytest.raises(HTTPException) as exc_info:
                await service.delete_title(sample_book.id)

        assert exc_info.value.status_code == 400
        assert "emprestada" in exc_info.value.detail


# ==========================================
# LoanService Tests
# ==========================================

@pytest.fixture
def sample_copy(sample_book):
    """Cópia de exemplo."""
    copy = BookCopy(
        id=uuid.uuid4(),
        book_title_id=sample_book.id,
        status=CopyStatus.AVAILABLE,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    copy.book_title = sample_book
    return copy


@pytest.fixture
def sample_loan(sample_user, sample_copy):
    """Empréstimo de exemplo."""
    now = datetime.now(timezone.utc)
    loan = Loan(
        id=uuid.uuid4(),
        user_id=sample_user.id,
        book_copy_id=sample_copy.id,
        loaned_at=now,
        due_date=now + timedelta(days=LOAN_PERIOD_DAYS),
        returned_at=None,
        fine_amount_final=None,
        renewals_count=0,
        created_at=now,
        updated_at=now,
    )
    loan.user = sample_user
    loan.book_copy = sample_copy
    return loan


class TestLoanService:
    """Testes para LoanService."""

    # ==========================================
    # Teste: Limite de 3 empréstimos ativos
    # ==========================================

    @pytest.mark.anyio
    async def test_create_loan_max_active_limit(self, mock_db, sample_user, sample_book):
        """Deve falhar quando usuário já tem 3 empréstimos ativos."""
        service = LoanService(mock_db)

        # Simular que usuário já tem MAX_ACTIVE_LOANS empréstimos ativos
        with patch.object(service.loan_repo, 'count_active_by_user', return_value=MAX_ACTIVE_LOANS):
            with pytest.raises(HTTPException) as exc_info:
                await service.create_loan(sample_user, sample_book.id)

        assert exc_info.value.status_code == 400
        assert f"{MAX_ACTIVE_LOANS}" in exc_info.value.detail
        assert "empréstimos ativos" in exc_info.value.detail

    @pytest.mark.anyio
    async def test_create_loan_below_limit_succeeds(self, mock_db, sample_user, sample_book, sample_copy):
        """Deve permitir empréstimo quando abaixo do limite."""
        service = LoanService(mock_db)

        sample_book.copies = [sample_copy]
        created_loan = Loan(
            id=uuid.uuid4(),
            user_id=sample_user.id,
            book_copy_id=sample_copy.id,
            loaned_at=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc) + timedelta(days=14),
            renewals_count=0,
        )
        created_loan.user = sample_user
        created_loan.book_copy = sample_copy

        with patch.object(service.loan_repo, 'count_active_by_user', return_value=2):
            with patch.object(service.title_repo, 'get_with_copies', return_value=sample_book):
                with patch.object(service.copy_repo, 'update_status', return_value=sample_copy):
                    with patch.object(service.loan_repo, 'get_with_relations', return_value=created_loan):
                        mock_db.add = MagicMock()
                        mock_db.commit = AsyncMock()
                        mock_db.refresh = AsyncMock()

                        result = await service.create_loan(sample_user, sample_book.id)

        assert result is not None
        assert result.user_id == sample_user.id

    # ==========================================
    # Teste: Livro não encontrado
    # ==========================================

    @pytest.mark.anyio
    async def test_create_loan_book_not_found(self, mock_db, sample_user):
        """Deve falhar quando livro não existe."""
        service = LoanService(mock_db)

        with patch.object(service.loan_repo, 'count_active_by_user', return_value=0):
            with patch.object(service.title_repo, 'get_with_copies', return_value=None):
                with pytest.raises(HTTPException) as exc_info:
                    await service.create_loan(sample_user, uuid.uuid4())

        assert exc_info.value.status_code == 404
        assert "Livro não encontrado" in exc_info.value.detail

    # ==========================================
    # Teste: Nenhuma cópia disponível
    # ==========================================

    @pytest.mark.anyio
    async def test_create_loan_no_available_copy(self, mock_db, sample_user, sample_book):
        """Deve falhar quando não há cópias disponíveis."""
        service = LoanService(mock_db)

        # Livro existe mas sem cópias disponíveis
        sample_book.copies = [
            BookCopy(
                id=uuid.uuid4(),
                book_title_id=sample_book.id,
                status=CopyStatus.LOANED,  # Todas emprestadas
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        ]

        with patch.object(service.loan_repo, 'count_active_by_user', return_value=0):
            with patch.object(service.title_repo, 'get_with_copies', return_value=sample_book):
                with pytest.raises(HTTPException) as exc_info:
                    await service.create_loan(sample_user, sample_book.id)

        assert exc_info.value.status_code == 400
        assert "Nenhuma cópia disponível" in exc_info.value.detail

    # ==========================================
    # Teste: Cálculo de multa
    # ==========================================

    def test_calculate_fine_no_delay(self):
        """Multa deve ser 0 quando não há atraso."""
        due_date = datetime.now(timezone.utc) + timedelta(days=1)  # Vence amanhã
        return_date = datetime.now(timezone.utc)  # Devolvendo hoje

        fine = LoanService.calculate_fine(due_date, return_date)

        assert fine == Decimal("0.00")

    def test_calculate_fine_with_delay(self):
        """Multa deve ser dias_atraso * R$ 2,00."""
        due_date = datetime.now(timezone.utc) - timedelta(days=5)  # Venceu há 5 dias
        return_date = datetime.now(timezone.utc)

        fine = LoanService.calculate_fine(due_date, return_date)

        expected_fine = Decimal("5") * FINE_PER_DAY  # 5 * R$ 2,00 = R$ 10,00
        assert fine == expected_fine

    def test_calculate_fine_10_days_late(self):
        """Multa para 10 dias de atraso deve ser R$ 20,00."""
        due_date = datetime.now(timezone.utc) - timedelta(days=10)
        return_date = datetime.now(timezone.utc)

        fine = LoanService.calculate_fine(due_date, return_date)

        assert fine == Decimal("20.00")

    # ==========================================
    # Teste: Devolução de livro
    # ==========================================

    @pytest.mark.anyio
    async def test_return_loan_success_no_fine(self, mock_db, sample_loan, sample_copy):
        """Deve devolver livro sem multa quando no prazo."""
        service = LoanService(mock_db)

        # Empréstimo não atrasado (due_date no futuro)
        sample_loan.due_date = datetime.now(timezone.utc) + timedelta(days=5)

        with patch.object(service.loan_repo, 'get_with_relations', return_value=sample_loan):
            with patch.object(service.copy_repo, 'get_by_id', return_value=sample_copy):
                with patch.object(service.copy_repo, 'update_status', return_value=sample_copy):
                    mock_db.commit = AsyncMock()

                    result = await service.return_loan(sample_loan.id)

        assert result.fine_applied == Decimal("0.00")
        assert "Sem multa" in result.message
        assert sample_loan.returned_at is not None

    @pytest.mark.anyio
    async def test_return_loan_with_fine(self, mock_db, sample_loan, sample_copy):
        """Deve calcular multa quando atrasado."""
        service = LoanService(mock_db)

        # Empréstimo atrasado (due_date no passado)
        sample_loan.due_date = datetime.now(timezone.utc) - timedelta(days=3)

        with patch.object(service.loan_repo, 'get_with_relations', return_value=sample_loan):
            with patch.object(service.copy_repo, 'get_by_id', return_value=sample_copy):
                with patch.object(service.copy_repo, 'update_status', return_value=sample_copy):
                    mock_db.commit = AsyncMock()

                    result = await service.return_loan(sample_loan.id)

        expected_fine = Decimal("3") * FINE_PER_DAY  # 3 * R$ 2,00 = R$ 6,00
        assert result.fine_applied == expected_fine
        assert "atraso" in result.message
        assert sample_loan.fine_amount_final == expected_fine

    @pytest.mark.anyio
    async def test_return_loan_already_returned(self, mock_db, sample_loan):
        """Deve falhar quando empréstimo já foi devolvido."""
        service = LoanService(mock_db)

        # Marcar como já devolvido
        sample_loan.returned_at = datetime.now(timezone.utc)

        with patch.object(service.loan_repo, 'get_with_relations', return_value=sample_loan):
            with pytest.raises(HTTPException) as exc_info:
                await service.return_loan(sample_loan.id)

        assert exc_info.value.status_code == 400
        assert "já foi devolvido" in exc_info.value.detail

    @pytest.mark.anyio
    async def test_return_loan_not_found(self, mock_db):
        """Deve falhar quando empréstimo não existe."""
        service = LoanService(mock_db)

        with patch.object(service.loan_repo, 'get_with_relations', return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await service.return_loan(uuid.uuid4())

        assert exc_info.value.status_code == 404
        assert "não encontrado" in exc_info.value.detail

    # ==========================================
    # Teste: Verificação can_user_borrow
    # ==========================================

    @pytest.mark.anyio
    async def test_can_user_borrow_yes(self, mock_db):
        """Deve retornar True quando usuário pode emprestar."""
        service = LoanService(mock_db)

        with patch.object(service.loan_repo, 'count_active_by_user', return_value=1):
            can_borrow, message = await service.can_user_borrow(uuid.uuid4())

        assert can_borrow is True
        assert "1/3" in message

    @pytest.mark.anyio
    async def test_can_user_borrow_no(self, mock_db):
        """Deve retornar False quando usuário atingiu limite."""
        service = LoanService(mock_db)

        with patch.object(service.loan_repo, 'count_active_by_user', return_value=MAX_ACTIVE_LOANS):
            can_borrow, message = await service.can_user_borrow(uuid.uuid4())

        assert can_borrow is False
        assert "Limite" in message

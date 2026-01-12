"""
Testes unitários para services (mockando session).
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.user import User
from app.models.author import Author
from app.models.book import BookTitle, BookCopy
from app.models.enums import UserRole, CopyStatus
from app.schemas.user import UserCreate, UserUpdate
from app.schemas.author import AuthorCreate, AuthorUpdate
from app.schemas.book import BookTitleCreate
from app.services.user import UserService
from app.services.author import AuthorService
from app.services.book import BookService


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

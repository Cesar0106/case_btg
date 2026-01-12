"""
Service para lógica de negócio de BookTitle e BookCopy.
"""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import BookTitle, BookCopy
from app.models.enums import CopyStatus
from app.repositories.author import AuthorRepository
from app.repositories.book import BookTitleRepository, BookCopyRepository
from app.schemas.book import (
    BookTitleCreate,
    BookTitleUpdate,
    BookTitleDetail,
    BookCopyCreate,
)


class BookService:
    """Service para operações de BookTitle e BookCopy."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.title_repo = BookTitleRepository(db)
        self.copy_repo = BookCopyRepository(db)
        self.author_repo = AuthorRepository(db)

    # ==========================================
    # BookTitle operations
    # ==========================================

    async def get_title_by_id(self, book_id: UUID) -> BookTitle:
        """
        Busca título por ID.

        Raises:
            HTTPException 404: Livro não encontrado
        """
        book = await self.title_repo.get_with_author(book_id)
        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Livro não encontrado",
            )
        return book

    async def get_title_detail(self, book_id: UUID) -> BookTitleDetail:
        """
        Busca título com detalhes (autor, contagem de cópias).

        Raises:
            HTTPException 404: Livro não encontrado
        """
        book = await self.title_repo.get_with_author(book_id)
        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Livro não encontrado",
            )

        counts = await self.copy_repo.count_by_title(book_id)

        return BookTitleDetail(
            id=book.id,
            title=book.title,
            author_id=book.author_id,
            author_name=book.author.name,
            published_year=book.published_year,
            pages=book.pages,
            total_copies=counts["total"],
            available_copies=counts["available"],
            created_at=book.created_at,
            updated_at=book.updated_at,
        )

    async def create_title_with_copies(
        self,
        data: BookTitleCreate,
        quantity: int = 1,
    ) -> tuple[BookTitle, list[BookCopy]]:
        """
        Cria título e gera N cópias.

        Args:
            data: Dados do título
            quantity: Número de cópias a criar (padrão 1)

        Returns:
            Tupla (título, lista de cópias)

        Raises:
            HTTPException 404: Autor não encontrado
            HTTPException 400: Quantidade inválida
        """
        if quantity < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Quantidade deve ser pelo menos 1",
            )

        # Verifica se autor existe
        author = await self.author_repo.get_by_id(data.author_id)
        if not author:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Autor não encontrado",
            )

        # Cria título
        book = await self.title_repo.create(
            title=data.title,
            author_id=data.author_id,
            published_year=data.published_year,
            pages=data.pages,
        )

        # Cria cópias
        copies = await self.copy_repo.create_copies(book.id, quantity)

        # Recarrega com relacionamentos
        book = await self.title_repo.get_with_author(book.id)

        return book, copies

    async def update_title(
        self,
        book_id: UUID,
        data: BookTitleUpdate,
    ) -> BookTitle:
        """
        Atualiza título.

        Raises:
            HTTPException 404: Livro ou autor não encontrado
        """
        book = await self.get_title_by_id(book_id)

        if data.author_id and data.author_id != book.author_id:
            author = await self.author_repo.get_by_id(data.author_id)
            if not author:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Autor não encontrado",
                )

        return await self.title_repo.update(
            book,
            title=data.title,
            author_id=data.author_id,
            published_year=data.published_year,
            pages=data.pages,
        )

    async def delete_title(self, book_id: UUID) -> None:
        """
        Remove título e suas cópias.

        Raises:
            HTTPException 404: Livro não encontrado
            HTTPException 400: Existem cópias emprestadas
        """
        book = await self.title_repo.get_with_copies(book_id)
        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Livro não encontrado",
            )

        # Verifica se há cópias emprestadas
        loaned = [c for c in book.copies if c.status == CopyStatus.LOANED]
        if loaned:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Não é possível remover livro com {len(loaned)} cópia(s) emprestada(s)",
            )

        await self.title_repo.delete(book)

    async def list_titles(
        self,
        title: str | None = None,
        author_id: UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[BookTitle], int]:
        """Lista títulos com filtros e paginação."""
        return await self.title_repo.search(
            title=title,
            author_id=author_id,
            page=page,
            page_size=page_size,
        )

    # ==========================================
    # BookCopy operations
    # ==========================================

    async def get_copy_by_id(self, copy_id: UUID) -> BookCopy:
        """
        Busca cópia por ID.

        Raises:
            HTTPException 404: Cópia não encontrada
        """
        copy = await self.copy_repo.get_by_id(copy_id)
        if not copy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cópia não encontrada",
            )
        return copy

    async def add_copies(
        self,
        book_id: UUID,
        quantity: int,
    ) -> list[BookCopy]:
        """
        Adiciona mais cópias a um título existente.

        Raises:
            HTTPException 404: Livro não encontrado
            HTTPException 400: Quantidade inválida
        """
        if quantity < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Quantidade deve ser pelo menos 1",
            )

        # Verifica se livro existe
        await self.get_title_by_id(book_id)

        return await self.copy_repo.create_copies(book_id, quantity)

    async def list_copies(self, book_id: UUID) -> list[BookCopy]:
        """Lista todas as cópias de um título."""
        await self.get_title_by_id(book_id)
        return await self.copy_repo.get_by_title(book_id)

    async def get_available_copy(self, book_id: UUID) -> BookCopy | None:
        """Retorna uma cópia disponível do título, se houver."""
        copies = await self.copy_repo.get_available_by_title(book_id)
        return copies[0] if copies else None

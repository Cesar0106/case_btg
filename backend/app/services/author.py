"""
Service para lógica de negócio de Author.
"""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.author import Author
from app.repositories.author import AuthorRepository
from app.schemas.author import AuthorCreate, AuthorUpdate


class AuthorService:
    """Service para operações de Author."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AuthorRepository(db)

    async def get_by_id(self, author_id: UUID) -> Author:
        """
        Busca autor por ID.

        Raises:
            HTTPException 404: Autor não encontrado
        """
        author = await self.repo.get_by_id(author_id)
        if not author:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Autor não encontrado",
            )
        return author

    async def get_with_books(self, author_id: UUID) -> Author:
        """
        Busca autor com seus livros.

        Raises:
            HTTPException 404: Autor não encontrado
        """
        author = await self.repo.get_with_books(author_id)
        if not author:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Autor não encontrado",
            )
        return author

    async def create(self, data: AuthorCreate) -> Author:
        """Cria novo autor."""
        return await self.repo.create(name=data.name)

    async def update(self, author_id: UUID, data: AuthorUpdate) -> Author:
        """
        Atualiza autor.

        Raises:
            HTTPException 404: Autor não encontrado
        """
        author = await self.get_by_id(author_id)
        return await self.repo.update(author, name=data.name)

    async def delete(self, author_id: UUID) -> None:
        """
        Remove autor.

        Raises:
            HTTPException 404: Autor não encontrado
            HTTPException 400: Autor possui livros cadastrados
        """
        author = await self.repo.get_with_books(author_id)
        if not author:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Autor não encontrado",
            )

        if author.books:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Não é possível remover autor com livros cadastrados",
            )

        await self.repo.delete(author)

    async def list_paginated(
        self,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
    ) -> tuple[list[Author], int]:
        """Lista autores com paginação e filtro."""
        return await self.repo.get_all_paginated(page, page_size, search)

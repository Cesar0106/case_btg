"""
Repository para operações de Author no banco de dados.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.author import Author
from app.repositories.base import BaseRepository


class AuthorRepository(BaseRepository[Author]):
    """Repository para operações CRUD de Author."""

    def __init__(self, db: AsyncSession):
        super().__init__(Author, db)

    async def get_by_name(self, name: str) -> Author | None:
        """Busca autor por nome exato."""
        result = await self.db.execute(
            select(Author).where(Author.name == name)
        )
        return result.scalar_one_or_none()

    async def search_by_name(self, name: str) -> list[Author]:
        """Busca autores por nome (parcial, case insensitive)."""
        result = await self.db.execute(
            select(Author).where(Author.name.ilike(f"%{name}%"))
        )
        return list(result.scalars().all())

    async def get_with_books(self, author_id) -> Author | None:
        """Busca autor com seus livros carregados."""
        result = await self.db.execute(
            select(Author)
            .where(Author.id == author_id)
            .options(selectinload(Author.books))
        )
        return result.scalar_one_or_none()

    async def get_all_paginated(
        self,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
    ) -> tuple[list[Author], int]:
        """
        Lista autores com paginação e filtro opcional.

        Args:
            page: Número da página
            page_size: Tamanho da página
            search: Termo de busca no nome

        Returns:
            Tupla (lista de autores, total)
        """
        skip = (page - 1) * page_size

        query = select(Author)
        count_query = select(Author)

        if search:
            query = query.where(Author.name.ilike(f"%{search}%"))
            count_query = count_query.where(Author.name.ilike(f"%{search}%"))

        # Total com filtros
        count_result = await self.db.execute(
            select(func.count()).select_from(count_query.subquery())
        )
        total = count_result.scalar_one()

        # Resultados paginados
        result = await self.db.execute(
            query
            .offset(skip)
            .limit(page_size)
            .order_by(Author.name)
        )
        authors = list(result.scalars().all())

        return authors, total

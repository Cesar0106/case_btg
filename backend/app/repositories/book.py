"""
Repository para operações de BookTitle e BookCopy no banco de dados.
"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.book import BookTitle, BookCopy
from app.models.enums import CopyStatus
from app.repositories.base import BaseRepository


class BookTitleRepository(BaseRepository[BookTitle]):
    """Repository para operações CRUD de BookTitle."""

    def __init__(self, db: AsyncSession):
        super().__init__(BookTitle, db)

    async def get_with_author(self, book_id: UUID) -> BookTitle | None:
        """Busca título com dados do autor."""
        result = await self.db.execute(
            select(BookTitle)
            .where(BookTitle.id == book_id)
            .options(selectinload(BookTitle.author))
        )
        return result.scalar_one_or_none()

    async def get_with_copies(self, book_id: UUID) -> BookTitle | None:
        """Busca título com suas cópias."""
        result = await self.db.execute(
            select(BookTitle)
            .where(BookTitle.id == book_id)
            .options(
                selectinload(BookTitle.author),
                selectinload(BookTitle.copies),
            )
        )
        return result.scalar_one_or_none()

    async def search(
        self,
        title: str | None = None,
        author_id: UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[BookTitle], int]:
        """
        Busca títulos com filtros e paginação.

        Args:
            title: Filtro por título (parcial)
            author_id: Filtro por autor
            page: Número da página
            page_size: Tamanho da página

        Returns:
            Tupla (lista de títulos, total)
        """
        skip = (page - 1) * page_size

        query = select(BookTitle).options(selectinload(BookTitle.author))
        count_query = select(BookTitle)

        if title:
            query = query.where(BookTitle.title.ilike(f"%{title}%"))
            count_query = count_query.where(BookTitle.title.ilike(f"%{title}%"))

        if author_id:
            query = query.where(BookTitle.author_id == author_id)
            count_query = count_query.where(BookTitle.author_id == author_id)

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
            .order_by(BookTitle.title)
        )
        books = list(result.scalars().all())

        return books, total

    async def get_by_author(self, author_id: UUID) -> list[BookTitle]:
        """Lista todos os títulos de um autor."""
        result = await self.db.execute(
            select(BookTitle)
            .where(BookTitle.author_id == author_id)
            .order_by(BookTitle.title)
        )
        return list(result.scalars().all())


class BookCopyRepository(BaseRepository[BookCopy]):
    """Repository para operações CRUD de BookCopy."""

    def __init__(self, db: AsyncSession):
        super().__init__(BookCopy, db)

    async def create_copies(
        self,
        book_title_id: UUID,
        quantity: int,
    ) -> list[BookCopy]:
        """Cria múltiplas cópias de um título."""
        copies = []
        for _ in range(quantity):
            copy = BookCopy(
                book_title_id=book_title_id,
                status=CopyStatus.AVAILABLE,
            )
            self.db.add(copy)
            copies.append(copy)

        await self.db.commit()

        # Refresh all copies
        for copy in copies:
            await self.db.refresh(copy)

        return copies

    async def get_by_title(self, book_title_id: UUID) -> list[BookCopy]:
        """Lista todas as cópias de um título."""
        result = await self.db.execute(
            select(BookCopy)
            .where(BookCopy.book_title_id == book_title_id)
            .order_by(BookCopy.created_at)
        )
        return list(result.scalars().all())

    async def get_available_by_title(self, book_title_id: UUID) -> list[BookCopy]:
        """Lista cópias disponíveis de um título."""
        result = await self.db.execute(
            select(BookCopy)
            .where(
                BookCopy.book_title_id == book_title_id,
                BookCopy.status == CopyStatus.AVAILABLE,
            )
        )
        return list(result.scalars().all())

    async def count_by_title(self, book_title_id: UUID) -> dict[str, int]:
        """
        Conta cópias por status para um título.

        Returns:
            Dict com total, available, loaned, on_hold
        """
        result = await self.db.execute(
            select(BookCopy.status, func.count(BookCopy.id))
            .where(BookCopy.book_title_id == book_title_id)
            .group_by(BookCopy.status)
        )
        counts = {status.value: 0 for status in CopyStatus}
        for status, count in result.all():
            counts[status.value] = count

        total = sum(counts.values())
        return {
            "total": total,
            "available": counts.get(CopyStatus.AVAILABLE.value, 0),
            "loaned": counts.get(CopyStatus.LOANED.value, 0),
            "on_hold": counts.get(CopyStatus.ON_HOLD.value, 0),
        }

    async def update_status(
        self,
        copy: BookCopy,
        status: CopyStatus,
        hold_reservation_id: UUID | None = None,
        hold_expires_at=None,
    ) -> BookCopy:
        """Atualiza status de uma cópia."""
        copy.status = status
        copy.hold_reservation_id = hold_reservation_id
        copy.hold_expires_at = hold_expires_at
        await self.db.commit()
        await self.db.refresh(copy)
        return copy

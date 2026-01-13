"""
Repository para operações de Loan no banco de dados.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.loan import Loan
from app.models.book import BookCopy
from app.repositories.base import BaseRepository


class LoanRepository(BaseRepository[Loan]):
    """Repository para operações CRUD de Loan."""

    def __init__(self, db: AsyncSession):
        super().__init__(Loan, db)

    async def get_with_relations(self, loan_id: UUID) -> Loan | None:
        """Busca empréstimo com usuário e cópia do livro."""
        result = await self.db.execute(
            select(Loan)
            .where(Loan.id == loan_id)
            .options(
                selectinload(Loan.user),
                selectinload(Loan.book_copy).selectinload(BookCopy.book_title),
            )
        )
        return result.scalar_one_or_none()

    async def count_active_by_user(self, user_id: UUID) -> int:
        """Conta empréstimos ativos de um usuário."""
        result = await self.db.execute(
            select(func.count(Loan.id))
            .where(
                Loan.user_id == user_id,
                Loan.returned_at.is_(None),
            )
        )
        return result.scalar_one()

    async def get_active_by_user(self, user_id: UUID) -> list[Loan]:
        """Lista empréstimos ativos de um usuário."""
        result = await self.db.execute(
            select(Loan)
            .where(
                Loan.user_id == user_id,
                Loan.returned_at.is_(None),
            )
            .options(
                selectinload(Loan.book_copy).selectinload(BookCopy.book_title),
            )
            .order_by(Loan.due_date)
        )
        return list(result.scalars().all())

    async def get_active_by_copy(self, book_copy_id: UUID) -> Loan | None:
        """Busca empréstimo ativo de uma cópia específica."""
        result = await self.db.execute(
            select(Loan)
            .where(
                Loan.book_copy_id == book_copy_id,
                Loan.returned_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def search(
        self,
        user_id: UUID | None = None,
        book_title_id: UUID | None = None,
        status: str | None = None,  # "active", "returned", "overdue"
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Loan], int]:
        """
        Busca empréstimos com filtros e paginação.

        Args:
            user_id: Filtro por usuário
            book_title_id: Filtro por título do livro
            status: "active" (não devolvido), "returned", "overdue" (ativo e atrasado)
            page: Número da página
            page_size: Tamanho da página

        Returns:
            Tupla (lista de empréstimos, total)
        """
        skip = (page - 1) * page_size
        now = datetime.utcnow()

        # Query base com joins
        query = (
            select(Loan)
            .options(
                selectinload(Loan.user),
                selectinload(Loan.book_copy).selectinload(BookCopy.book_title),
            )
        )
        count_query = select(Loan)

        # Filtro por usuário
        if user_id:
            query = query.where(Loan.user_id == user_id)
            count_query = count_query.where(Loan.user_id == user_id)

        # Filtro por título do livro (precisa join com book_copy)
        if book_title_id:
            query = query.join(BookCopy).where(BookCopy.book_title_id == book_title_id)
            count_query = count_query.join(BookCopy).where(
                BookCopy.book_title_id == book_title_id
            )

        # Filtro por status
        if status == "active":
            query = query.where(Loan.returned_at.is_(None))
            count_query = count_query.where(Loan.returned_at.is_(None))
        elif status == "returned":
            query = query.where(Loan.returned_at.is_not(None))
            count_query = count_query.where(Loan.returned_at.is_not(None))
        elif status == "overdue":
            query = query.where(
                and_(
                    Loan.returned_at.is_(None),
                    Loan.due_date < now,
                )
            )
            count_query = count_query.where(
                and_(
                    Loan.returned_at.is_(None),
                    Loan.due_date < now,
                )
            )

        # Total com filtros
        count_result = await self.db.execute(
            select(func.count()).select_from(count_query.subquery())
        )
        total = count_result.scalar_one()

        # Resultados paginados
        result = await self.db.execute(
            query.offset(skip).limit(page_size).order_by(Loan.loaned_at.desc())
        )
        loans = list(result.scalars().all())

        return loans, total

    async def get_overdue_loans(self) -> list[Loan]:
        """Lista todos os empréstimos atrasados (para jobs/relatórios)."""
        now = datetime.utcnow()
        result = await self.db.execute(
            select(Loan)
            .where(
                Loan.returned_at.is_(None),
                Loan.due_date < now,
            )
            .options(
                selectinload(Loan.user),
                selectinload(Loan.book_copy).selectinload(BookCopy.book_title),
            )
            .order_by(Loan.due_date)
        )
        return list(result.scalars().all())

    async def get_earliest_due_date_by_title(self, book_title_id: UUID) -> datetime | None:
        """
        Retorna a menor due_date dos empréstimos ativos de um título.

        Args:
            book_title_id: ID do título do livro

        Returns:
            Menor due_date ou None se não houver empréstimos ativos
        """
        result = await self.db.execute(
            select(func.min(Loan.due_date))
            .join(BookCopy)
            .where(
                BookCopy.book_title_id == book_title_id,
                Loan.returned_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

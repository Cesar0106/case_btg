"""
Repository para operações de Reservation no banco de dados.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.reservation import Reservation
from app.models.enums import ReservationStatus
from app.repositories.base import BaseRepository


class ReservationRepository(BaseRepository[Reservation]):
    """Repository para operações CRUD de Reservation."""

    def __init__(self, db: AsyncSession):
        super().__init__(Reservation, db)

    async def get_with_relations(self, reservation_id: UUID) -> Reservation | None:
        """Busca reserva com usuário e título do livro."""
        result = await self.db.execute(
            select(Reservation)
            .where(Reservation.id == reservation_id)
            .options(
                selectinload(Reservation.user),
                selectinload(Reservation.book_title),
            )
        )
        return result.scalar_one_or_none()

    async def get_active_by_user_and_title(
        self,
        user_id: UUID,
        book_title_id: UUID,
    ) -> Reservation | None:
        """
        Busca reserva ativa (ACTIVE ou ON_HOLD) de um usuário para um título.

        Usado para verificar duplicatas antes de criar nova reserva.
        """
        result = await self.db.execute(
            select(Reservation)
            .where(
                Reservation.user_id == user_id,
                Reservation.book_title_id == book_title_id,
                Reservation.status.in_([
                    ReservationStatus.ACTIVE,
                    ReservationStatus.ON_HOLD,
                ]),
            )
        )
        return result.scalar_one_or_none()

    async def get_first_active_by_title(self, book_title_id: UUID) -> Reservation | None:
        """
        Busca a primeira reserva ACTIVE de um título (mais antiga por created_at).

        Usada para processar holds quando uma cópia fica disponível.
        """
        result = await self.db.execute(
            select(Reservation)
            .where(
                Reservation.book_title_id == book_title_id,
                Reservation.status == ReservationStatus.ACTIVE,
            )
            .order_by(Reservation.created_at.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def count_active_by_user(self, user_id: UUID) -> int:
        """Conta reservas ativas (ACTIVE ou ON_HOLD) de um usuário."""
        result = await self.db.execute(
            select(func.count(Reservation.id))
            .where(
                Reservation.user_id == user_id,
                Reservation.status.in_([
                    ReservationStatus.ACTIVE,
                    ReservationStatus.ON_HOLD,
                ]),
            )
        )
        return result.scalar_one()

    async def get_by_user(
        self,
        user_id: UUID,
        status: ReservationStatus | None = None,
    ) -> list[Reservation]:
        """Lista reservas de um usuário, opcionalmente filtradas por status."""
        query = (
            select(Reservation)
            .where(Reservation.user_id == user_id)
            .options(selectinload(Reservation.book_title))
            .order_by(Reservation.created_at.desc())
        )

        if status:
            query = query.where(Reservation.status == status)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_expired_holds(self) -> list[Reservation]:
        """
        Busca reservas ON_HOLD com hold_expires_at expirado.

        Usada pelo job de expiração de holds.
        """
        now = datetime.utcnow()
        result = await self.db.execute(
            select(Reservation)
            .where(
                Reservation.status == ReservationStatus.ON_HOLD,
                Reservation.hold_expires_at < now,
            )
            .options(selectinload(Reservation.book_title))
        )
        return list(result.scalars().all())

    async def get_titles_with_active_reservations(self) -> list[UUID]:
        """
        Retorna IDs de títulos que têm reservas ACTIVE.

        Usada para processar holds globalmente.
        """
        result = await self.db.execute(
            select(Reservation.book_title_id)
            .where(Reservation.status == ReservationStatus.ACTIVE)
            .distinct()
        )
        return list(result.scalars().all())

    async def update_status(
        self,
        reservation: Reservation,
        status: ReservationStatus,
        hold_expires_at: datetime | None = None,
    ) -> Reservation:
        """Atualiza status de uma reserva."""
        reservation.status = status
        reservation.hold_expires_at = hold_expires_at
        await self.db.commit()
        await self.db.refresh(reservation)
        return reservation

    async def search(
        self,
        user_id: UUID | None = None,
        book_title_id: UUID | None = None,
        status: ReservationStatus | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Reservation], int]:
        """
        Busca reservas com filtros e paginação.

        Args:
            user_id: Filtro por usuário
            book_title_id: Filtro por título
            status: Filtro por status
            page: Número da página
            page_size: Tamanho da página

        Returns:
            Tupla (lista de reservas, total)
        """
        skip = (page - 1) * page_size

        query = (
            select(Reservation)
            .options(
                selectinload(Reservation.user),
                selectinload(Reservation.book_title),
            )
        )
        count_query = select(Reservation)

        if user_id:
            query = query.where(Reservation.user_id == user_id)
            count_query = count_query.where(Reservation.user_id == user_id)

        if book_title_id:
            query = query.where(Reservation.book_title_id == book_title_id)
            count_query = count_query.where(Reservation.book_title_id == book_title_id)

        if status:
            query = query.where(Reservation.status == status)
            count_query = count_query.where(Reservation.status == status)

        count_result = await self.db.execute(
            select(func.count()).select_from(count_query.subquery())
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            query.offset(skip).limit(page_size).order_by(Reservation.created_at.desc())
        )
        reservations = list(result.scalars().all())

        return reservations, total

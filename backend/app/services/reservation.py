"""
Service para lógica de negócio de Reservation.

Regras de negócio:
    - Reserva só é permitida se NÃO há cópia disponível
    - Reserva só é permitida se expected_due_date <= now + 24h
    - Quando cópia fica disponível, primeira reserva ACTIVE vira ON_HOLD
    - Hold expira após 24 horas
    - Se hold expira, próxima reserva da fila é processada
"""

from datetime import datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.reservation import Reservation
from app.models.enums import ReservationStatus, CopyStatus
from app.repositories.reservation import ReservationRepository
from app.repositories.book import BookTitleRepository, BookCopyRepository
from app.repositories.loan import LoanRepository
from app.schemas.reservation import (
    HOLD_DURATION_HOURS,
    ReservationDetail,
    ReservationCreateResponse,
    ReservationCancelResponse,
    HoldProcessResult,
    ExpireHoldsResult,
)


class ReservationService:
    """Service para operações de Reservation."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.reservation_repo = ReservationRepository(db)
        self.title_repo = BookTitleRepository(db)
        self.copy_repo = BookCopyRepository(db)
        self.loan_repo = LoanRepository(db)

    async def create_reservation(
        self,
        user: User,
        book_title_id: UUID,
    ) -> ReservationCreateResponse:
        """
        Cria uma nova reserva para um título.

        Regras:
            1. Se existe cópia AVAILABLE -> negar (orientar a emprestar)
            2. Calcular expected_due_date (menor due_date de loans ativos)
            3. Permitir somente se expected_due_date existe
            4. Criar reservation ACTIVE

        Args:
            user: Usuário que está fazendo a reserva
            book_title_id: ID do título a reservar

        Returns:
            ReservationCreateResponse com detalhes da reserva

        Raises:
            HTTPException 404: Livro não encontrado
            HTTPException 400: Cópia disponível (deve emprestar diretamente)
            HTTPException 400: Reserva duplicada
            HTTPException 400: Não há empréstimos ativos (nada a reservar)
        """
        book = await self.title_repo.get_by_id(book_title_id)
        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Livro não encontrado",
            )

        counts = await self.copy_repo.count_by_title(book_title_id)
        if counts["available"] > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Há cópias disponíveis. Faça um empréstimo diretamente.",
            )

        if counts["total"] == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Este título não possui cópias cadastradas.",
            )

        expected_due_date = await self.loan_repo.get_earliest_due_date_by_title(
            book_title_id
        )
        if expected_due_date is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Não há empréstimos ativos para este título. "
                       "Aguarde o cadastro de novas cópias.",
            )

        existing = await self.reservation_repo.get_active_by_user_and_title(
            user.id,
            book_title_id,
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Você já possui uma reserva ativa para este título.",
            )

        reservation = Reservation(
            user_id=user.id,
            book_title_id=book_title_id,
            status=ReservationStatus.ACTIVE,
        )
        self.db.add(reservation)
        await self.db.commit()
        await self.db.refresh(reservation)

        reservation = await self.reservation_repo.get_with_relations(reservation.id)

        queue_position = await self._get_queue_position(reservation)

        return ReservationCreateResponse(
            reservation=ReservationDetail.from_reservation(
                reservation,
                queue_position=queue_position,
            ),
            message=f"Reserva criada com sucesso. Posição na fila: {queue_position}",
            expected_available_at=expected_due_date,
        )

    async def cancel_reservation(
        self,
        user: User,
        reservation_id: UUID,
        is_admin: bool = False,
    ) -> ReservationCancelResponse:
        """
        Cancela uma reserva.

        Args:
            user: Usuário solicitando o cancelamento
            reservation_id: ID da reserva
            is_admin: Se True, permite cancelar qualquer reserva

        Returns:
            ReservationCancelResponse

        Raises:
            HTTPException 404: Reserva não encontrada
            HTTPException 403: Sem permissão
            HTTPException 400: Reserva não pode ser cancelada
        """
        reservation = await self.reservation_repo.get_with_relations(reservation_id)
        if not reservation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reserva não encontrada",
            )

        if not is_admin and reservation.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você não tem permissão para cancelar esta reserva",
            )

        if not reservation.can_be_cancelled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Reserva com status {reservation.status.value} não pode ser cancelada",
            )

        if reservation.status == ReservationStatus.ON_HOLD:
            await self._release_hold_copy(reservation)

        reservation = await self.reservation_repo.update_status(
            reservation,
            ReservationStatus.CANCELLED,
        )

        return ReservationCancelResponse(
            reservation=ReservationDetail.from_reservation(reservation),
            message="Reserva cancelada com sucesso",
        )

    async def process_holds(
        self,
        book_title_id: UUID | None = None,
    ) -> list[HoldProcessResult]:
        """
        Processa holds para títulos com cópias disponíveis.

        Se book_title_id é fornecido, processa apenas esse título.
        Caso contrário, processa todos os títulos com reservas ACTIVE.

        Regras:
            - Se existe cópia AVAILABLE e há reservas ACTIVE:
              - Pega a reserva mais antiga ACTIVE
              - Escolhe uma cópia e seta status ON_HOLD
              - Define hold_expires_at = now + 24h
              - Marca reservation ON_HOLD

        Args:
            book_title_id: ID do título (opcional)

        Returns:
            Lista de HoldProcessResult para cada hold processado
        """
        results = []

        if book_title_id:
            title_ids = [book_title_id]
        else:
            title_ids = await self.reservation_repo.get_titles_with_active_reservations()

        for title_id in title_ids:
            result = await self._process_single_title_hold(title_id)
            if result:
                results.append(result)

        return results

    async def expire_holds(self) -> ExpireHoldsResult:
        """
        Expira holds que passaram do prazo.

        Para cada cópia ON_HOLD com hold_expires_at < now:
            1. Libera cópia (status = AVAILABLE)
            2. Marca reserva como EXPIRED
            3. Processa próximo hold da fila

        Returns:
            ExpireHoldsResult com contadores
        """
        expired_reservations = await self.reservation_repo.get_expired_holds()
        expired_count = 0
        titles_to_process = set()

        for reservation in expired_reservations:
            await self._release_hold_copy(reservation)

            await self.reservation_repo.update_status(
                reservation,
                ReservationStatus.EXPIRED,
            )

            titles_to_process.add(reservation.book_title_id)
            expired_count += 1

        next_holds_processed = 0
        for title_id in titles_to_process:
            result = await self._process_single_title_hold(title_id)
            if result:
                next_holds_processed += 1

        return ExpireHoldsResult(
            expired_count=expired_count,
            next_holds_processed=next_holds_processed,
            message=f"Expirados: {expired_count}, Novos holds: {next_holds_processed}",
        )

    async def get_reservation_detail(
        self,
        reservation_id: UUID,
    ) -> ReservationDetail:
        """
        Busca detalhes de uma reserva.

        Raises:
            HTTPException 404: Reserva não encontrada
        """
        reservation = await self.reservation_repo.get_with_relations(reservation_id)
        if not reservation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reserva não encontrada",
            )

        queue_position = None
        if reservation.status == ReservationStatus.ACTIVE:
            queue_position = await self._get_queue_position(reservation)

        return ReservationDetail.from_reservation(reservation, queue_position)

    async def get_user_reservations(
        self,
        user_id: UUID,
        status_filter: ReservationStatus | None = None,
    ) -> list[ReservationDetail]:
        """Lista reservas de um usuário."""
        reservations = await self.reservation_repo.get_by_user(user_id, status_filter)

        results = []
        for reservation in reservations:
            queue_position = None
            if reservation.status == ReservationStatus.ACTIVE:
                queue_position = await self._get_queue_position(reservation)
            results.append(
                ReservationDetail.from_reservation(reservation, queue_position)
            )

        return results

    async def _process_single_title_hold(
        self,
        book_title_id: UUID,
    ) -> HoldProcessResult | None:
        """
        Processa hold para um único título.

        Returns:
            HoldProcessResult se um hold foi criado, None caso contrário
        """
        available_copies = await self.copy_repo.get_available_by_title(book_title_id)
        if not available_copies:
            return None

        first_reservation = await self.reservation_repo.get_first_active_by_title(
            book_title_id
        )
        if not first_reservation:
            return None

        copy = available_copies[0]
        now = datetime.utcnow()
        hold_expires_at = now + timedelta(hours=HOLD_DURATION_HOURS)

        copy = await self.copy_repo.update_status(
            copy,
            CopyStatus.ON_HOLD,
            hold_reservation_id=first_reservation.id,
            hold_expires_at=hold_expires_at,
        )

        first_reservation = await self.reservation_repo.update_status(
            first_reservation,
            ReservationStatus.ON_HOLD,
            hold_expires_at=hold_expires_at,
        )

        return HoldProcessResult(
            reservation_id=first_reservation.id,
            book_copy_id=copy.id,
            hold_expires_at=hold_expires_at,
            message=f"Cópia separada. Retire até {hold_expires_at.isoformat()}",
        )

    async def _release_hold_copy(self, reservation: Reservation) -> None:
        """
        Libera a cópia associada a um hold.

        Busca cópias ON_HOLD com hold_reservation_id = reservation.id
        e as marca como AVAILABLE.
        """
        copies = await self.copy_repo.get_by_title(reservation.book_title_id)
        for copy in copies:
            if (
                copy.status == CopyStatus.ON_HOLD
                and copy.hold_reservation_id == reservation.id
            ):
                await self.copy_repo.update_status(
                    copy,
                    CopyStatus.AVAILABLE,
                    hold_reservation_id=None,
                    hold_expires_at=None,
                )
                break

    async def _get_queue_position(self, reservation: Reservation) -> int:
        """
        Calcula a posição na fila de uma reserva ACTIVE.

        Retorna 1 para a primeira da fila.
        """
        if reservation.status != ReservationStatus.ACTIVE:
            return 0

        reservations, _ = await self.reservation_repo.search(
            book_title_id=reservation.book_title_id,
            status=ReservationStatus.ACTIVE,
            page=1,
            page_size=1000,
        )

        sorted_reservations = sorted(reservations, key=lambda r: r.created_at)

        for i, res in enumerate(sorted_reservations, start=1):
            if res.id == reservation.id:
                return i

        return 0

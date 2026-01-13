"""
Schemas Pydantic para Reservation.
"""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.models.enums import ReservationStatus
from app.schemas.base import BaseSchema, TimestampSchema


HOLD_DURATION_HOURS = 24


class ReservationCreate(BaseSchema):
    """Schema para criação de reserva."""
    book_title_id: UUID


class ReservationRead(TimestampSchema):
    """Schema para leitura de reserva."""
    id: UUID
    user_id: UUID
    book_title_id: UUID
    status: ReservationStatus
    hold_expires_at: datetime | None = None


class ReservationDetail(ReservationRead):
    """Schema com detalhes expandidos."""
    user_name: str
    book_title: str
    queue_position: int | None = Field(
        None,
        description="Posição na fila (apenas para ACTIVE)",
    )

    @classmethod
    def from_reservation(
        cls,
        reservation,
        queue_position: int | None = None,
    ) -> "ReservationDetail":
        """Constrói a partir de um model Reservation."""
        return cls(
            id=reservation.id,
            user_id=reservation.user_id,
            book_title_id=reservation.book_title_id,
            status=reservation.status,
            hold_expires_at=reservation.hold_expires_at,
            created_at=reservation.created_at,
            updated_at=reservation.updated_at,
            user_name=reservation.user.name if reservation.user else "Unknown",
            book_title=reservation.book_title.title if reservation.book_title else "Unknown",
            queue_position=queue_position,
        )


class ReservationCreateResponse(BaseSchema):
    """Resposta da criação de reserva."""
    reservation: ReservationDetail
    message: str
    expected_available_at: datetime | None = Field(
        None,
        description="Data esperada de disponibilidade baseada no menor due_date",
    )


class ReservationCancelResponse(BaseSchema):
    """Resposta do cancelamento de reserva."""
    reservation: ReservationDetail
    message: str


class HoldProcessResult(BaseSchema):
    """Resultado do processamento de hold."""
    reservation_id: UUID
    book_title_id: UUID
    book_copy_id: UUID
    hold_expires_at: datetime
    message: str


class ExpireHoldsResult(BaseSchema):
    """Resultado da expiração de holds."""
    expired_count: int
    next_holds_processed: int
    affected_book_title_ids: list[UUID] = Field(
        default_factory=list,
        description="IDs dos títulos afetados (para invalidação de cache)",
    )
    message: str

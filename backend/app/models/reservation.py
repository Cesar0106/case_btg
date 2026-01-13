"""
Model de reserva de livros.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, DateTime, Index, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import UUIDMixin, TimestampMixin
from app.models.enums import ReservationStatus

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.book import BookTitle


class Reservation(Base, UUIDMixin, TimestampMixin):
    """
    Reserva de um título de livro por um usuário.

    Fluxo de estados:
        1. ACTIVE: Usuário entra na fila de espera
        2. ON_HOLD: Cópia disponível, separada para o usuário
        3. FULFILLED: Usuário retirou o livro (criou empréstimo)
        4. EXPIRED: Expirou na fila ou não retirou a tempo
        5. CANCELLED: Usuário cancelou a reserva

    Regras de negócio:
        - Reserva é por título (book_title_id), não por cópia
        - Quando cópia fica disponível, primeira reserva ACTIVE vira ON_HOLD
        - Hold expira após período configurável (ex: 48h)
        - Se hold expirar, próxima reserva da fila é ativada

    Attributes:
        id: UUID único da reserva
        user_id: FK para o usuário que fez a reserva
        book_title_id: FK para o título reservado
        status: Status atual da reserva
        created_at: Data/hora da criação (posição na fila)
        hold_expires_at: Data/hora limite para retirada (quando ON_HOLD)
    """
    __tablename__ = "reservations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    book_title_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("book_titles.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[ReservationStatus] = mapped_column(
        SQLEnum(ReservationStatus, name="reservation_status", create_type=True),
        nullable=False,
        default=ReservationStatus.ACTIVE,
    )
    hold_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="reservations",
        lazy="selectin",
    )
    book_title: Mapped["BookTitle"] = relationship(
        "BookTitle",
        back_populates="reservations",
        lazy="selectin",
    )

    # Índices para queries frequentes
    __table_args__ = (
        # Buscar reservas de um usuário
        Index("ix_reservations_user_id", "user_id"),
        # Buscar reservas de um título
        Index("ix_reservations_book_title_id", "book_title_id"),
        # Buscar reservas por status
        Index("ix_reservations_status", "status"),
        # Buscar reservas ativas de um título (fila ordenada por created_at)
        Index("ix_reservations_title_active", "book_title_id", "status", "created_at"),
        # Buscar reservas on_hold que podem expirar
        Index("ix_reservations_hold_expires", "status", "hold_expires_at"),
        # Evitar reserva duplicada ativa do mesmo usuário para mesmo título
        Index(
            "ix_reservations_user_title_active",
            "user_id",
            "book_title_id",
            "status",
            unique=False,  # Constraint será via lógica de negócio
        ),
    )

    def __repr__(self) -> str:
        return f"<Reservation {self.id} - {self.status.value}>"

    @property
    def is_active(self) -> bool:
        """Retorna True se a reserva está ativa (ACTIVE ou ON_HOLD)."""
        return self.status in (ReservationStatus.ACTIVE, ReservationStatus.ON_HOLD)

    @property
    def is_on_hold(self) -> bool:
        """Retorna True se a reserva está em hold."""
        return self.status == ReservationStatus.ON_HOLD

    @property
    def is_hold_expired(self) -> bool:
        """Retorna True se o hold expirou."""
        if self.status != ReservationStatus.ON_HOLD:
            return False
        if self.hold_expires_at is None:
            return False
        return datetime.utcnow() > self.hold_expires_at.replace(tzinfo=None)

    @property
    def can_be_cancelled(self) -> bool:
        """Retorna True se a reserva pode ser cancelada."""
        return self.status in (ReservationStatus.ACTIVE, ReservationStatus.ON_HOLD)

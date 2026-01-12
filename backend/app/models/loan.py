"""
Model de empréstimo de livros.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Integer, DateTime, Numeric, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import UUIDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.book import BookCopy


class Loan(Base, UUIDMixin, TimestampMixin):
    """
    Empréstimo de uma cópia de livro para um usuário.

    Regras de negócio:
        - Prazo padrão: 14 dias
        - Multa por atraso: R$ 2,00/dia
        - Máximo de renovações: configurável (padrão 2)
        - Usuário pode ter no máximo 3 empréstimos ativos

    Attributes:
        id: UUID único do empréstimo
        user_id: FK para o usuário que fez o empréstimo
        book_copy_id: FK para a cópia física emprestada
        loaned_at: Data/hora do empréstimo
        due_date: Data de devolução prevista
        returned_at: Data/hora da devolução efetiva (null se não devolvido)
        fine_amount_final: Valor final da multa calculado na devolução
        renewals_count: Número de renovações realizadas
    """
    __tablename__ = "loans"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    book_copy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("book_copies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    loaned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )
    due_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    returned_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    fine_amount_final: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    renewals_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="loans",
        lazy="selectin",
    )
    book_copy: Mapped["BookCopy"] = relationship(
        "BookCopy",
        back_populates="loans",
        lazy="selectin",
    )

    # Índices compostos e simples para queries frequentes
    __table_args__ = (
        Index("ix_loans_user_id", "user_id"),
        Index("ix_loans_book_copy_id", "book_copy_id"),
        Index("ix_loans_due_date", "due_date"),
        Index("ix_loans_returned_at", "returned_at"),
        # Índice para buscar empréstimos ativos de um usuário
        Index("ix_loans_user_active", "user_id", "returned_at"),
        # Índice para buscar empréstimos atrasados
        Index("ix_loans_overdue", "due_date", "returned_at"),
    )

    def __repr__(self) -> str:
        status = "returned" if self.returned_at else "active"
        return f"<Loan {self.id} - {status}>"

    @property
    def is_active(self) -> bool:
        """Retorna True se o empréstimo ainda está ativo (não devolvido)."""
        return self.returned_at is None

    @property
    def is_overdue(self) -> bool:
        """Retorna True se o empréstimo está atrasado."""
        if self.returned_at:
            return False
        return datetime.utcnow() > self.due_date.replace(tzinfo=None)

    @property
    def days_overdue(self) -> int:
        """Retorna número de dias em atraso (0 se não atrasado)."""
        if not self.is_overdue:
            return 0
        delta = datetime.utcnow() - self.due_date.replace(tzinfo=None)
        return max(0, delta.days)

"""
Models de livros: BookTitle (título) e BookCopy (cópia física).
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import ForeignKey, Integer, String, DateTime
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import UUIDMixin, TimestampMixin
from app.models.enums import CopyStatus

if TYPE_CHECKING:
    from app.models.author import Author
    from app.models.loan import Loan
    from app.models.reservation import Reservation


class BookTitle(Base, UUIDMixin, TimestampMixin):
    """
    Título de um livro (obra).

    Um título pode ter múltiplas cópias físicas (BookCopy).

    Attributes:
        id: UUID único do título
        title: Título do livro
        author_id: FK para o autor
        published_year: Ano de publicação (opcional)
        pages: Número de páginas (opcional)
        copies: Lista de cópias físicas deste título
    """
    __tablename__ = "book_titles"

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("authors.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    published_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pages: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    author: Mapped["Author"] = relationship(
        "Author",
        back_populates="books",
        lazy="selectin",
    )
    copies: Mapped[List["BookCopy"]] = relationship(
        "BookCopy",
        back_populates="book_title",
        lazy="selectin",
    )
    reservations: Mapped[List["Reservation"]] = relationship(
        "Reservation",
        back_populates="book_title",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<BookTitle {self.title}>"


class BookCopy(Base, UUIDMixin, TimestampMixin):
    """
    Cópia física de um livro.

    Representa uma unidade do inventário que pode ser emprestada.

    Attributes:
        id: UUID único da cópia
        book_title_id: FK para o título do livro
        status: AVAILABLE, LOANED ou ON_HOLD
        hold_reservation_id: ID da reserva que está em hold (se ON_HOLD)
        hold_expires_at: Data/hora de expiração do hold
    """
    __tablename__ = "book_copies"

    book_title_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("book_titles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[CopyStatus] = mapped_column(
        ENUM(CopyStatus, name="copy_status", create_type=True),
        nullable=False,
        default=CopyStatus.AVAILABLE,
        index=True,
    )
    hold_reservation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    hold_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    book_title: Mapped["BookTitle"] = relationship(
        "BookTitle",
        back_populates="copies",
        lazy="selectin",
    )
    loans: Mapped[List["Loan"]] = relationship(
        "Loan",
        back_populates="book_copy",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<BookCopy {self.id} - {self.status.value}>"

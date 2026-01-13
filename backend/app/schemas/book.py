"""
Schemas Pydantic para BookTitle e BookCopy.
"""

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from app.models.enums import CopyStatus
from app.schemas.base import BaseSchema, TimestampSchema


# ============================================
# BookTitle Schemas
# ============================================

class BookTitleCreate(BaseSchema):
    """Schema para criação de título de livro."""
    title: str = Field(..., min_length=1, max_length=500, examples=["Dom Casmurro"])
    author_id: UUID
    published_year: int | None = Field(None, ge=1000, le=2100, examples=[1899])
    pages: int | None = Field(None, ge=1, le=50000, examples=[256])

    @field_validator("published_year")
    @classmethod
    def validate_year(cls, v: int | None) -> int | None:
        if v is not None and v > datetime.utcnow().year:
            raise ValueError("Ano de publicação não pode ser no futuro")
        return v


class BookTitleRead(TimestampSchema):
    """Schema para leitura de título de livro."""
    id: UUID
    title: str
    author_id: UUID
    published_year: int | None
    pages: int | None


class BookTitleUpdate(BaseSchema):
    """Schema para atualização de título de livro."""
    title: str | None = Field(None, min_length=1, max_length=500)
    author_id: UUID | None = None
    published_year: int | None = Field(None, ge=1000, le=2100)
    pages: int | None = Field(None, ge=1, le=50000)


class BookTitleWithAuthor(BookTitleRead):
    """Título com dados do autor."""
    author_name: str


class BookTitleDetail(BookTitleRead):
    """Título com autor e contagem de cópias."""
    author_name: str
    total_copies: int
    available_copies: int


# ============================================
# BookCopy Schemas
# ============================================

class BookCopyCreate(BaseSchema):
    """Schema para criação de cópia de livro."""
    book_title_id: UUID


class BookCopyRead(TimestampSchema):
    """Schema para leitura de cópia de livro."""
    id: UUID
    book_title_id: UUID
    status: CopyStatus
    hold_reservation_id: UUID | None
    hold_expires_at: datetime | None


class BookCopyUpdate(BaseSchema):
    """Schema para atualização de cópia de livro."""
    status: CopyStatus | None = None


class BookCopyWithTitle(BookCopyRead):
    """Cópia com dados do título."""
    book_title: str
    author_name: str


# ============================================
# Availability Schema
# ============================================

class BookAvailability(BaseSchema):
    """
    Resposta de disponibilidade de um título.

    Campos:
        available: True se há cópia disponível para empréstimo
        reason: Motivo se não disponível
        expected_due_date: Menor due_date dos empréstimos ativos (se houver)
    """
    book_title_id: UUID
    available: bool
    reason: str | None = None
    expected_due_date: datetime | None = None
    available_copies: int
    total_copies: int

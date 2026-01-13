"""
Schemas Pydantic para Author.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import Field

from app.schemas.base import BaseSchema, TimestampSchema

if TYPE_CHECKING:
    from app.schemas.book import BookTitleRead


class AuthorCreate(BaseSchema):
    """Schema para criação de autor."""
    name: str = Field(..., min_length=2, max_length=255, examples=["Machado de Assis"])


class AuthorRead(TimestampSchema):
    """Schema para leitura de autor."""
    id: UUID
    name: str


class AuthorUpdate(BaseSchema):
    """Schema para atualização de autor."""
    name: str | None = Field(None, min_length=2, max_length=255)


class AuthorWithBooks(AuthorRead):
    """Autor com lista de livros (para detalhes)."""
    books: list[BookTitleRead] = []

    model_config = {"from_attributes": True}


# Rebuild model para resolver forward references
from app.schemas.book import BookTitleRead  # noqa: E402, F811
AuthorWithBooks.model_rebuild()

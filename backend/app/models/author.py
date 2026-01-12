"""
Model de autor de livros.
"""

from typing import TYPE_CHECKING, List

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import UUIDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.book import BookTitle


class Author(Base, UUIDMixin, TimestampMixin):
    """
    Autor de livros.

    Attributes:
        id: UUID único do autor
        name: Nome do autor
        books: Lista de títulos do autor
    """
    __tablename__ = "authors"

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Relationships
    books: Mapped[List["BookTitle"]] = relationship(
        "BookTitle",
        back_populates="author",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Author {self.name}>"

"""
Models SQLAlchemy da aplicação.

Importar todos os models aqui para que o Alembic detecte as mudanças.
"""

from app.models.enums import UserRole, CopyStatus
from app.models.user import User
from app.models.author import Author
from app.models.book import BookTitle, BookCopy

__all__ = [
    "UserRole",
    "CopyStatus",
    "User",
    "Author",
    "BookTitle",
    "BookCopy",
]

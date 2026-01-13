"""
Models SQLAlchemy da aplicação.

Importar todos os models aqui para que o Alembic detecte as mudanças.
"""

from app.models.enums import UserRole, CopyStatus, ReservationStatus
from app.models.user import User
from app.models.author import Author
from app.models.book import BookTitle, BookCopy
from app.models.loan import Loan
from app.models.reservation import Reservation

__all__ = [
    "UserRole",
    "CopyStatus",
    "ReservationStatus",
    "User",
    "Author",
    "BookTitle",
    "BookCopy",
    "Loan",
    "Reservation",
]

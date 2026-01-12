"""
Enums utilizados nos models da aplicação.
"""

import enum


class UserRole(str, enum.Enum):
    """Roles de usuário no sistema."""
    ADMIN = "ADMIN"
    USER = "USER"


class CopyStatus(str, enum.Enum):
    """Status de uma cópia física do livro."""
    AVAILABLE = "AVAILABLE"
    LOANED = "LOANED"
    ON_HOLD = "ON_HOLD"

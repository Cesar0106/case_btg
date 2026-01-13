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


class ReservationStatus(str, enum.Enum):
    """
    Status de uma reserva de livro.

    Fluxo típico:
        ACTIVE -> ON_HOLD -> FULFILLED (sucesso)
        ACTIVE -> EXPIRED (expirou na fila)
        ON_HOLD -> EXPIRED (não retirou a tempo)
        ACTIVE/ON_HOLD -> CANCELLED (cancelada pelo usuário)
    """
    ACTIVE = "ACTIVE"        # Na fila, aguardando cópia
    ON_HOLD = "ON_HOLD"      # Cópia separada, aguardando retirada
    FULFILLED = "FULFILLED"  # Convertida em empréstimo
    EXPIRED = "EXPIRED"      # Expirou (fila ou hold)
    CANCELLED = "CANCELLED"  # Cancelada pelo usuário

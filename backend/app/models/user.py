"""
Model de usuário do sistema.
"""

from typing import TYPE_CHECKING, List

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import UUIDMixin, TimestampMixin
from app.models.enums import UserRole

if TYPE_CHECKING:
    from app.models.loan import Loan
    from app.models.reservation import Reservation


class User(Base, UUIDMixin, TimestampMixin):
    """
    Usuário do sistema de biblioteca.

    Attributes:
        id: UUID único do usuário
        name: Nome completo
        email: Email único (usado como login)
        password_hash: Hash bcrypt da senha
        role: ADMIN ou USER
        created_at: Data de criação
        updated_at: Data de última atualização
        loans: Lista de empréstimos do usuário
    """
    __tablename__ = "users"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        ENUM(UserRole, name="user_role", create_type=True),
        nullable=False,
        default=UserRole.USER,
    )

    # Relationships
    loans: Mapped[List["Loan"]] = relationship(
        "Loan",
        back_populates="user",
        lazy="selectin",
    )
    reservations: Mapped[List["Reservation"]] = relationship(
        "Reservation",
        back_populates="user",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<User {self.email}>"

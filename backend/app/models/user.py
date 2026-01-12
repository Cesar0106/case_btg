"""
Model de usuário do sistema.
"""

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.base import UUIDMixin, TimestampMixin
from app.models.enums import UserRole


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

    def __repr__(self) -> str:
        return f"<User {self.email}>"

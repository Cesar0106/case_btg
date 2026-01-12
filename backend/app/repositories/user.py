"""
Repository para operações de User no banco de dados.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.enums import UserRole


class UserRepository:
    """Repository para operações CRUD de User."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: UUID) -> User | None:
        """Busca usuário por ID."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        """Busca usuário por email."""
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def email_exists(self, email: str) -> bool:
        """Verifica se email já está cadastrado."""
        user = await self.get_by_email(email)
        return user is not None

    async def create(
        self,
        name: str,
        email: str,
        password_hash: str,
        role: UserRole = UserRole.USER,
    ) -> User:
        """Cria novo usuário."""
        user = User(
            name=name,
            email=email,
            password_hash=password_hash,
            role=role,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def count(self) -> int:
        """Conta total de usuários."""
        from sqlalchemy import func
        result = await self.db.execute(select(func.count(User.id)))
        return result.scalar_one()

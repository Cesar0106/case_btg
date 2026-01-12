"""
Repository para operações de User no banco de dados.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.enums import UserRole
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository para operações CRUD de User."""

    def __init__(self, db: AsyncSession):
        super().__init__(User, db)

    async def get_by_email(self, email: str) -> User | None:
        """Busca usuário por email."""
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def email_exists(self, email: str) -> bool:
        """Verifica se email já está cadastrado."""
        user = await self.get_by_email(email)
        return user is not None

    async def create_user(
        self,
        name: str,
        email: str,
        password_hash: str,
        role: UserRole = UserRole.USER,
    ) -> User:
        """Cria novo usuário."""
        return await self.create(
            name=name,
            email=email,
            password_hash=password_hash,
            role=role,
        )

    async def get_all_paginated(
        self,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[User], int]:
        """
        Lista usuários com paginação.

        Returns:
            Tupla (lista de usuários, total)
        """
        skip = (page - 1) * page_size
        users = await self.get_all(skip=skip, limit=page_size)
        total = await self.count()
        return users, total

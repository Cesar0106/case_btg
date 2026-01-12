"""
Service para lógica de negócio de User.
"""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User
from app.models.enums import UserRole
from app.repositories.user import UserRepository
from app.schemas.user import UserCreate, UserUpdate
from app.schemas.base import PaginatedResponse


class UserService:
    """Service para operações de User."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = UserRepository(db)

    async def get_by_id(self, user_id: UUID) -> User:
        """
        Busca usuário por ID.

        Raises:
            HTTPException 404: Usuário não encontrado
        """
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário não encontrado",
            )
        return user

    async def get_by_email(self, email: str) -> User | None:
        """Busca usuário por email."""
        return await self.repo.get_by_email(email)

    async def create(self, data: UserCreate, role: UserRole = UserRole.USER) -> User:
        """
        Cria novo usuário.

        Raises:
            HTTPException 400: Email já cadastrado
        """
        if await self.repo.email_exists(data.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email já cadastrado",
            )

        password_hash = hash_password(data.password)
        return await self.repo.create_user(
            name=data.name,
            email=data.email,
            password_hash=password_hash,
            role=role,
        )

    async def update(self, user_id: UUID, data: UserUpdate) -> User:
        """
        Atualiza usuário.

        Raises:
            HTTPException 404: Usuário não encontrado
            HTTPException 400: Email já cadastrado por outro usuário
        """
        user = await self.get_by_id(user_id)

        if data.email and data.email != user.email:
            if await self.repo.email_exists(data.email):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email já cadastrado",
                )

        return await self.repo.update(
            user,
            name=data.name,
            email=data.email,
        )

    async def list_paginated(
        self,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[User], int]:
        """Lista usuários com paginação."""
        return await self.repo.get_all_paginated(page, page_size)

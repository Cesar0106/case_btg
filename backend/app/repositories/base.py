"""
Repository base com operações CRUD genéricas.
"""

from typing import Any, Generic, Type, TypeVar
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Repository base com operações CRUD.

    Fornece métodos genéricos para:
    - get_by_id: Buscar por ID
    - get_all: Listar todos (paginado)
    - create: Criar registro
    - update: Atualizar registro
    - delete: Remover registro
    - count: Contar registros
    """

    def __init__(self, model: Type[ModelType], db: AsyncSession):
        self.model = model
        self.db = db

    async def get_by_id(self, id: UUID) -> ModelType | None:
        """Busca registro por ID."""
        result = await self.db.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ModelType]:
        """Lista registros com paginação."""
        result = await self.db.execute(
            select(self.model)
            .offset(skip)
            .limit(limit)
            .order_by(self.model.created_at.desc())
        )
        return list(result.scalars().all())

    async def create(self, **kwargs: Any) -> ModelType:
        """Cria novo registro."""
        instance = self.model(**kwargs)
        self.db.add(instance)
        await self.db.commit()
        await self.db.refresh(instance)
        return instance

    async def update(
        self,
        instance: ModelType,
        **kwargs: Any,
    ) -> ModelType:
        """Atualiza registro existente."""
        for key, value in kwargs.items():
            if value is not None:
                setattr(instance, key, value)
        await self.db.commit()
        await self.db.refresh(instance)
        return instance

    async def delete(self, instance: ModelType) -> None:
        """Remove registro."""
        await self.db.delete(instance)
        await self.db.commit()

    async def count(self) -> int:
        """Conta total de registros."""
        result = await self.db.execute(
            select(func.count(self.model.id))
        )
        return result.scalar_one()

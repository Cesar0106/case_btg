"""
Schemas base reutilizáveis em toda a aplicação.
"""

from datetime import datetime
from typing import Generic, List, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class BaseSchema(BaseModel):
    """Schema base com configurações padrão."""
    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
    )


class TimestampSchema(BaseSchema):
    """Schema com timestamps."""
    created_at: datetime
    updated_at: datetime


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Resposta paginada genérica.

    Uso nos endpoints:
        @app.get("/users", response_model=PaginatedResponse[UserRead])
        async def list_users(...) -> PaginatedResponse[UserRead]:
            ...
    """
    items: List[T]
    total: int
    page: int
    page_size: int
    pages: int

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def create(
        cls,
        items: List[T],
        total: int,
        page: int,
        page_size: int,
    ) -> "PaginatedResponse[T]":
        """Factory method para criar resposta paginada."""
        pages = (total + page_size - 1) // page_size if page_size > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )


class ErrorDetail(BaseModel):
    """Detalhe de um erro."""
    field: str | None = None
    message: str


class ErrorResponse(BaseModel):
    """
    Resposta de erro padrão.

    Uso:
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error="validation_error",
                message="Dados inválidos",
                details=[ErrorDetail(field="email", message="Email já existe")]
            ).model_dump()
        )
    """
    error: str
    message: str
    details: List[ErrorDetail] | None = None


class MessageResponse(BaseModel):
    """Resposta simples com mensagem."""
    message: str

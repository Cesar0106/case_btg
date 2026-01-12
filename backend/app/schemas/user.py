"""
Schemas Pydantic para User.
"""

import re
from datetime import datetime
from uuid import UUID

from pydantic import EmailStr, Field, field_validator

from app.models.enums import UserRole
from app.schemas.base import BaseSchema, TimestampSchema


class UserCreate(BaseSchema):
    """
    Schema para criação de usuário (sign-up).

    Validações:
        - name: 2-255 caracteres
        - email: formato válido
        - password: mínimo 8 chars, 1 maiúscula, 1 minúscula, 1 número
    """
    name: str = Field(..., min_length=2, max_length=255, examples=["João Silva"])
    email: EmailStr = Field(..., examples=["joao@email.com"])
    password: str = Field(..., min_length=8, max_length=128, examples=["Senha123!"])

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Valida complexidade da senha."""
        if not re.search(r"[A-Z]", v):
            raise ValueError("Senha deve conter pelo menos uma letra maiúscula")
        if not re.search(r"[a-z]", v):
            raise ValueError("Senha deve conter pelo menos uma letra minúscula")
        if not re.search(r"\d", v):
            raise ValueError("Senha deve conter pelo menos um número")
        return v


class UserRead(TimestampSchema):
    """
    Schema para leitura de usuário.

    Retornado nos endpoints GET. Nunca expõe password_hash.
    """
    id: UUID
    name: str
    email: EmailStr
    role: UserRole


class UserUpdate(BaseSchema):
    """Schema para atualização de usuário."""
    name: str | None = Field(None, min_length=2, max_length=255)
    email: EmailStr | None = None


class UserLogin(BaseSchema):
    """Schema para login."""
    email: EmailStr
    password: str


class TokenResponse(BaseSchema):
    """Resposta de autenticação com token JWT."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserWithToken(BaseSchema):
    """Usuário com token JWT (retorno do login)."""
    user: UserRead
    token: TokenResponse

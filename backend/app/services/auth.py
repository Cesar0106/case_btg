"""
Service de autenticação.
"""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.models.enums import UserRole
from app.repositories.user import UserRepository
from app.schemas.user import UserCreate, UserRead, TokenResponse, UserWithToken

settings = get_settings()


class AuthService:
    """Service para operações de autenticação."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)

    async def signup(self, data: UserCreate) -> User:
        """
        Registra novo usuário.

        Args:
            data: Dados do novo usuário

        Returns:
            Usuário criado

        Raises:
            HTTPException 400: Email já cadastrado
        """
        if await self.user_repo.email_exists(data.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email já cadastrado",
            )

        password_hash = hash_password(data.password)
        user = await self.user_repo.create(
            name=data.name,
            email=data.email,
            password_hash=password_hash,
            role=UserRole.USER,
        )
        return user

    async def login(self, email: str, password: str) -> UserWithToken:
        """
        Autentica usuário e retorna token JWT.

        Args:
            email: Email do usuário
            password: Senha em texto plano

        Returns:
            Usuário com token JWT

        Raises:
            HTTPException 401: Credenciais inválidas
        """
        user = await self.user_repo.get_by_email(email)

        if user is None or not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email ou senha incorretos",
                headers={"WWW-Authenticate": "Bearer"},
            )

        access_token = create_access_token(
            subject=str(user.id),
            extra_data={"role": user.role.value},
        )

        return UserWithToken(
            user=UserRead.model_validate(user),
            token=TokenResponse(
                access_token=access_token,
                token_type="bearer",
                expires_in=settings.JWT_EXPIRES_MINUTES * 60,
            ),
        )

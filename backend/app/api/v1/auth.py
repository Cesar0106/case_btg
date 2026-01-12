"""
Endpoints de autenticação.
"""

from fastapi import APIRouter, status

from app.core.deps import DbSession, CurrentUser
from app.schemas.user import UserCreate, UserLogin, UserRead, UserWithToken
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/signup",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar novo usuário",
    description="Cria uma nova conta de usuário. Email deve ser único.",
)
async def signup(data: UserCreate, db: DbSession) -> UserRead:
    """
    Registro público de usuário.

    - **name**: Nome completo (2-255 caracteres)
    - **email**: Email único (será usado como login)
    - **password**: Mínimo 8 caracteres, 1 maiúscula, 1 minúscula, 1 número
    """
    service = AuthService(db)
    user = await service.signup(data)
    return UserRead.model_validate(user)


@router.post(
    "/login",
    response_model=UserWithToken,
    summary="Autenticar usuário",
    description="Retorna token JWT para autenticação nos endpoints protegidos.",
)
async def login(data: UserLogin, db: DbSession) -> UserWithToken:
    """
    Login de usuário.

    Retorna access_token JWT para uso no header Authorization.

    Uso: `Authorization: Bearer <access_token>`
    """
    service = AuthService(db)
    return await service.login(data.email, data.password)


@router.get(
    "/me",
    response_model=UserRead,
    summary="Dados do usuário autenticado",
    description="Retorna os dados do usuário logado.",
)
async def get_me(current_user: CurrentUser) -> UserRead:
    """Retorna dados do usuário autenticado."""
    return UserRead.model_validate(current_user)

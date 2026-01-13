"""
Endpoints de Gestão de Usuários.

Contratos:
    - GET /users: Lista todos os usuários (ADMIN)
    - GET /users/{user_id}: Busca usuário por ID (ADMIN)
    - GET /users/{user_id}/loans: Lista empréstimos de um usuário (ADMIN)

Autorização:
    - Todos os endpoints requerem role ADMIN

Status codes:
    - 200: Sucesso
    - 401: Não autenticado
    - 403: Sem permissão (não é admin)
    - 404: Usuário não encontrado
"""

from uuid import UUID

from fastapi import APIRouter, Query, HTTPException
from fastapi import status as http_status
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.core.deps import DbSession, AdminUser
from app.models.user import User
from app.models.loan import Loan
from app.models.enums import UserRole
from app.schemas.base import PaginatedResponse
from app.schemas.user import UserRead

router = APIRouter(prefix="/users", tags=["Users"])


# ==========================================
# Schemas de resposta
# ==========================================

from datetime import datetime
from typing import Literal
from decimal import Decimal
from pydantic import BaseModel, computed_field


class UserWithStats(UserRead):
    """Usuário com estatísticas de empréstimos."""

    active_loans_count: int = 0
    total_loans_count: int = 0


class UserLoanResponse(BaseModel):
    """Resposta de empréstimo para listagem."""

    id: UUID
    book_copy_id: UUID
    loaned_at: datetime
    due_date: datetime
    returned_at: datetime | None = None
    renewals_count: int = 0
    fine_amount_final: Decimal | None = None

    # Informações do livro
    book_title: str | None = None
    book_author: str | None = None

    @computed_field
    @property
    def status(self) -> Literal["ACTIVE", "RETURNED"]:
        """Status derivado do empréstimo."""
        return "RETURNED" if self.returned_at else "ACTIVE"

    @computed_field
    @property
    def is_overdue(self) -> bool:
        """Verifica se está atrasado."""
        if self.returned_at:
            return False
        return datetime.utcnow() > self.due_date.replace(tzinfo=None)

    model_config = {"from_attributes": True}


# ==========================================
# Endpoints
# ==========================================

@router.get(
    "",
    response_model=PaginatedResponse[UserWithStats],
    summary="Listar todos os usuários",
    description="Lista todos os usuários do sistema com estatísticas. **Requer role ADMIN.**",
)
async def list_users(
    db: DbSession,
    admin: AdminUser,
    role: UserRole | None = Query(None, description="Filtrar por role"),
    search: str | None = Query(None, description="Buscar por nome ou email"),
    page: int = Query(1, ge=1, description="Número da página"),
    page_size: int = Query(20, ge=1, le=100, description="Itens por página"),
) -> PaginatedResponse[UserWithStats]:
    """
    Lista todos os usuários do sistema com paginação.

    Filtros:
        - role: ADMIN ou USER
        - search: busca parcial em nome ou email

    Inclui estatísticas:
        - active_loans_count: empréstimos ativos
        - total_loans_count: total de empréstimos
    """
    # Query base
    query = select(User)
    count_query = select(func.count(User.id))

    # Filtros
    if role:
        query = query.where(User.role == role)
        count_query = count_query.where(User.role == role)

    if search:
        search_filter = f"%{search}%"
        query = query.where(
            (User.name.ilike(search_filter)) | (User.email.ilike(search_filter))
        )
        count_query = count_query.where(
            (User.name.ilike(search_filter)) | (User.email.ilike(search_filter))
        )

    # Total
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginação
    offset = (page - 1) * page_size
    query = query.order_by(User.created_at.desc()).offset(offset).limit(page_size)

    # Executar
    result = await db.execute(query)
    users = result.scalars().all()

    # Buscar estatísticas de empréstimos para cada usuário
    items = []
    for user in users:
        # Contar empréstimos ativos
        active_count_result = await db.execute(
            select(func.count(Loan.id))
            .where(Loan.user_id == user.id)
            .where(Loan.returned_at.is_(None))
        )
        active_count = active_count_result.scalar() or 0

        # Contar total de empréstimos
        total_count_result = await db.execute(
            select(func.count(Loan.id))
            .where(Loan.user_id == user.id)
        )
        total_count = total_count_result.scalar() or 0

        user_data = UserRead.model_validate(user)
        items.append(UserWithStats(
            **user_data.model_dump(),
            active_loans_count=active_count,
            total_loans_count=total_count,
        ))

    return PaginatedResponse.create(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{user_id}",
    response_model=UserWithStats,
    summary="Buscar usuário por ID",
    description="Retorna dados de um usuário específico. **Requer role ADMIN.**",
)
async def get_user(
    user_id: UUID,
    db: DbSession,
    admin: AdminUser,
) -> UserWithStats:
    """
    Busca um usuário pelo ID.

    Retorna:
        Dados do usuário com estatísticas de empréstimos

    Raises:
        404: Usuário não encontrado
    """
    # Buscar usuário
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado",
        )

    # Contar empréstimos ativos
    active_count_result = await db.execute(
        select(func.count(Loan.id))
        .where(Loan.user_id == user.id)
        .where(Loan.returned_at.is_(None))
    )
    active_count = active_count_result.scalar() or 0

    # Contar total de empréstimos
    total_count_result = await db.execute(
        select(func.count(Loan.id))
        .where(Loan.user_id == user.id)
    )
    total_count = total_count_result.scalar() or 0

    user_data = UserRead.model_validate(user)
    return UserWithStats(
        **user_data.model_dump(),
        active_loans_count=active_count,
        total_loans_count=total_count,
    )


@router.get(
    "/{user_id}/loans",
    response_model=list[UserLoanResponse],
    summary="Listar empréstimos de um usuário",
    description="Lista todos os empréstimos de um usuário específico. **Requer role ADMIN.**",
)
async def get_user_loans(
    user_id: UUID,
    db: DbSession,
    admin: AdminUser,
    status_filter: str | None = Query(
        None,
        alias="status",
        pattern="^(active|returned|overdue)$",
        description="Filtro: active, returned, overdue",
    ),
) -> list[UserLoanResponse]:
    """
    Lista todos os empréstimos de um usuário específico.

    Filtros:
        - status: "active" (não devolvido), "returned", "overdue" (ativo e atrasado)

    Retorna:
        Lista de empréstimos com informações do livro

    Raises:
        404: Usuário não encontrado
    """
    # Verificar se usuário existe
    user_result = await db.execute(
        select(User.id).where(User.id == user_id)
    )
    if not user_result.scalar():
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado",
        )

    # Buscar empréstimos com relacionamentos
    from app.models.book import BookCopy, BookTitle
    from app.models.author import Author

    query = (
        select(Loan)
        .options(
            selectinload(Loan.book_copy).selectinload(BookCopy.book_title).selectinload(BookTitle.author)
        )
        .where(Loan.user_id == user_id)
        .order_by(Loan.loaned_at.desc())
    )

    # Aplicar filtros
    if status_filter == "active":
        query = query.where(Loan.returned_at.is_(None))
    elif status_filter == "returned":
        query = query.where(Loan.returned_at.isnot(None))
    elif status_filter == "overdue":
        query = query.where(
            Loan.returned_at.is_(None),
            Loan.due_date < datetime.utcnow(),
        )

    result = await db.execute(query)
    loans = result.scalars().all()

    # Construir resposta
    items = []
    for loan in loans:
        book_title = None
        book_author = None

        if loan.book_copy and loan.book_copy.book_title:
            book_title = loan.book_copy.book_title.title
            if loan.book_copy.book_title.author:
                book_author = loan.book_copy.book_title.author.name

        items.append(UserLoanResponse(
            id=loan.id,
            book_copy_id=loan.book_copy_id,
            loaned_at=loan.loaned_at,
            due_date=loan.due_date,
            returned_at=loan.returned_at,
            renewals_count=loan.renewals_count,
            fine_amount_final=loan.fine_amount_final,
            book_title=book_title,
            book_author=book_author,
        ))

    return items

"""
Endpoints de Empréstimos (Loan).

Contratos:
    - POST /loans: Cria empréstimo (usuário autenticado)
    - GET /loans: Lista empréstimos com filtros
    - GET /loans/{id}: Detalhes do empréstimo
    - PATCH /loans/{id}/return: Devolve livro

Autorização:
    - USER: vê apenas seus próprios empréstimos
    - ADMIN: vê todos os empréstimos

Status codes:
    - 200: Sucesso
    - 201: Criado com sucesso
    - 400: Erro de validação ou regra de negócio
    - 401: Não autenticado
    - 403: Sem permissão
    - 404: Empréstimo não encontrado
"""

from uuid import UUID

from fastapi import APIRouter, Query, status, HTTPException

from app.core.deps import DbSession, CurrentUser, AdminUser
from app.models.enums import UserRole
from app.schemas.base import PaginatedResponse
from app.schemas.loan import (
    LoanCreate,
    LoanDetail,
    LoanReturn,
    MAX_ACTIVE_LOANS,
)
from app.services.loan import LoanService

router = APIRouter(prefix="/loans", tags=["Loans"])


# ==========================================
# Schema de resposta estendido
# ==========================================

from datetime import datetime
from typing import Literal
from decimal import Decimal
from pydantic import BaseModel, computed_field


class LoanResponse(LoanDetail):
    """
    Resposta de empréstimo com status derivado.

    Inclui:
        - Todos os campos de LoanDetail
        - status: "ACTIVE" ou "RETURNED"
        - fine_amount_current: multa calculada dinamicamente
        - fine_amount_final: multa persistida (se devolvido)
    """

    @computed_field
    @property
    def status(self) -> Literal["ACTIVE", "RETURNED"]:
        """Status derivado do empréstimo."""
        return "RETURNED" if self.returned_at else "ACTIVE"

    @computed_field
    @property
    def fine_amount_current(self) -> Decimal:
        """Multa atual (dinâmica para ativos, final para devolvidos)."""
        return self.current_fine


# ==========================================
# Endpoints
# ==========================================

@router.post(
    "",
    response_model=LoanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar empréstimo",
    description=f"Cria um novo empréstimo. Limite: {MAX_ACTIVE_LOANS} empréstimos ativos por usuário.",
)
async def create_loan(
    data: LoanCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> LoanResponse:
    """
    Cria novo empréstimo para o usuário autenticado.

    Regras:
        - Máximo de 3 empréstimos ativos por usuário
        - Deve haver cópia disponível do título
        - Prazo: 14 dias

    Raises:
        400: Usuário já tem 3 empréstimos ativos
        400: Nenhuma cópia disponível
        404: Livro não encontrado
    """
    service = LoanService(db)
    loan = await service.create_loan(current_user, data.book_title_id)

    return LoanResponse.from_loan(loan)


@router.get(
    "",
    response_model=PaginatedResponse[LoanResponse],
    summary="Listar empréstimos",
    description="Lista empréstimos com filtros. USER vê apenas os próprios; ADMIN vê todos.",
)
async def list_loans(
    db: DbSession,
    current_user: CurrentUser,
    user_id: UUID | None = Query(None, description="Filtrar por usuário (apenas ADMIN)"),
    book_title_id: UUID | None = Query(None, description="Filtrar por título do livro"),
    status_filter: str | None = Query(
        None,
        alias="status",
        pattern="^(active|returned|overdue)$",
        description="Filtro: active, returned, overdue",
    ),
    page: int = Query(1, ge=1, description="Número da página"),
    page_size: int = Query(20, ge=1, le=100, description="Itens por página"),
) -> PaginatedResponse[LoanResponse]:
    """
    Lista empréstimos com paginação e filtros.

    Autorização:
        - USER: vê apenas seus próprios empréstimos (ignora user_id)
        - ADMIN: pode filtrar por qualquer user_id

    Filtros:
        - status: "active" (não devolvido), "returned", "overdue" (ativo e atrasado)
        - book_title_id: ID do título do livro
        - user_id: ID do usuário (apenas admin)
    """
    service = LoanService(db)

    # Autorização: USER só vê os próprios, ADMIN pode ver todos
    effective_user_id = user_id
    if current_user.role != UserRole.ADMIN:
        effective_user_id = current_user.id  # Força filtro pelo próprio usuário

    loans, total = await service.list_loans(
        user_id=effective_user_id,
        book_title_id=book_title_id,
        status_filter=status_filter,
        page=page,
        page_size=page_size,
    )

    # Converter para LoanResponse
    items = [LoanResponse.model_validate(loan.model_dump()) for loan in loans]

    return PaginatedResponse.create(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/my",
    response_model=list[LoanResponse],
    summary="Meus empréstimos ativos",
    description="Lista empréstimos ativos do usuário autenticado.",
)
async def my_active_loans(
    db: DbSession,
    current_user: CurrentUser,
) -> list[LoanResponse]:
    """
    Lista empréstimos ativos do usuário autenticado.

    Atalho conveniente para ver empréstimos pendentes de devolução.
    """
    service = LoanService(db)
    loans = await service.get_user_active_loans(current_user.id)

    return [LoanResponse.model_validate(loan.model_dump()) for loan in loans]


@router.get(
    "/overdue",
    response_model=list[LoanResponse],
    summary="Empréstimos atrasados",
    description="Lista todos os empréstimos atrasados. **Requer role ADMIN.**",
)
async def list_overdue_loans(
    db: DbSession,
    admin: AdminUser,
) -> list[LoanResponse]:
    """
    Lista todos os empréstimos atrasados no sistema.

    Apenas administradores podem acessar esta visão geral.
    Útil para relatórios e notificações.
    """
    service = LoanService(db)
    loans = await service.get_overdue_loans()

    return [LoanResponse.model_validate(loan.model_dump()) for loan in loans]


@router.get(
    "/{loan_id}",
    response_model=LoanResponse,
    summary="Detalhes do empréstimo",
    description="Retorna detalhes de um empréstimo específico.",
)
async def get_loan(
    loan_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> LoanResponse:
    """
    Retorna detalhes de um empréstimo.

    Autorização:
        - USER: apenas seus próprios empréstimos
        - ADMIN: qualquer empréstimo

    Raises:
        403: Usuário não tem permissão para ver este empréstimo
        404: Empréstimo não encontrado
    """
    service = LoanService(db)
    loan = await service.get_loan_detail(loan_id)

    # Verificar autorização
    if current_user.role != UserRole.ADMIN and loan.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para ver este empréstimo",
        )

    return LoanResponse.model_validate(loan.model_dump())


class LoanReturnResponse(BaseModel):
    """Resposta de devolução com loan estendido."""

    loan: LoanResponse
    fine_applied: Decimal
    message: str


@router.patch(
    "/{loan_id}/return",
    response_model=LoanReturnResponse,
    summary="Devolver livro",
    description="Processa a devolução de um livro emprestado.",
)
async def return_loan(
    loan_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> LoanReturnResponse:
    """
    Processa a devolução de um empréstimo.

    Fluxo:
        1. Verifica se empréstimo existe e pertence ao usuário (ou é admin)
        2. Calcula multa por atraso (R$ 2,00/dia)
        3. Marca como devolvido
        4. Libera cópia do livro

    Autorização:
        - USER: apenas seus próprios empréstimos
        - ADMIN: qualquer empréstimo

    Returns:
        Detalhes da devolução incluindo multa aplicada

    Raises:
        400: Empréstimo já foi devolvido
        403: Sem permissão
        404: Empréstimo não encontrado
    """
    service = LoanService(db)

    # Buscar empréstimo para verificar autorização
    loan = await service.get_loan_by_id(loan_id)

    # Verificar autorização
    if current_user.role != UserRole.ADMIN and loan.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para devolver este empréstimo",
        )

    # Processar devolução
    result = await service.return_loan(loan_id)

    # Construir resposta com LoanResponse
    loan_response = LoanResponse.model_validate(result.loan.model_dump())

    return LoanReturnResponse(
        loan=loan_response,
        fine_applied=result.fine_applied,
        message=result.message,
    )


class LoanRenewResponse(BaseModel):
    """Resposta de renovação com loan estendido."""

    loan: LoanResponse
    previous_due_date: datetime
    new_due_date: datetime
    message: str


@router.patch(
    "/{loan_id}/renew",
    response_model=LoanRenewResponse,
    summary="Renovar empréstimo",
    description="Renova um empréstimo ativo por mais 14 dias.",
)
async def renew_loan(
    loan_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> LoanRenewResponse:
    """
    Renova um empréstimo ativo.

    Regras:
        - Empréstimo deve estar ATIVO (não devolvido)
        - Máximo de 1 renovação permitida
        - Não pode estar atrasado (now <= due_date)
        - Não pode haver reservas ACTIVE/ON_HOLD para o título

    Ação:
        - due_date += 14 dias
        - renewals_count += 1

    Autorização:
        - Apenas o próprio usuário pode renovar seu empréstimo

    Returns:
        Detalhes da renovação incluindo novas datas

    Raises:
        400: Empréstimo já devolvido
        400: Limite de renovações atingido
        400: Empréstimo atrasado
        400: Há reservas pendentes para o título
        403: Sem permissão
        404: Empréstimo não encontrado
    """
    service = LoanService(db)

    # Processar renovação (validação de propriedade feita no service)
    result = await service.renew_loan(loan_id, current_user.id)

    # Construir resposta com LoanResponse
    loan_response = LoanResponse.model_validate(result.loan.model_dump())

    return LoanRenewResponse(
        loan=loan_response,
        previous_due_date=result.previous_due_date,
        new_due_date=result.new_due_date,
        message=result.message,
    )

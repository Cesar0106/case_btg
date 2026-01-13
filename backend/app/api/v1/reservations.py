"""
Endpoints de Reservas (Reservation).

Contratos:
    - POST /reservations: Cria reserva (usuário autenticado)
    - GET /reservations: Lista reservas com filtros
    - GET /reservations/{id}: Detalhes da reserva
    - PATCH /reservations/{id}/cancel: Cancela reserva

Autorização:
    - USER: vê apenas suas próprias reservas
    - ADMIN: vê todas as reservas

Rate Limiting aplicado:
    - POST /reservations: 60 req/min (rate_limit_default)

Status codes:
    - 200: Sucesso
    - 201: Criado com sucesso
    - 400: Erro de validação ou regra de negócio
    - 401: Não autenticado
    - 403: Sem permissão
    - 404: Reserva não encontrada
    - 429: Rate limit excedido
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status, HTTPException

from app.core.deps import DbSession, CurrentUser
from app.core.rate_limit import rate_limit_default
from app.models.enums import UserRole, ReservationStatus
from app.schemas.base import PaginatedResponse
from app.schemas.reservation import (
    ReservationCreate,
    ReservationDetail,
    ReservationCreateResponse,
    ReservationCancelResponse,
)
from app.services.reservation import ReservationService

router = APIRouter(prefix="/reservations", tags=["Reservations"])


@router.post(
    "",
    response_model=ReservationCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar reserva",
    description="Cria uma nova reserva para um título sem cópias disponíveis.",
)
async def create_reservation(
    data: ReservationCreate,
    db: DbSession,
    current_user: CurrentUser,
    request: Request,
    _: None = Depends(rate_limit_default),
) -> ReservationCreateResponse:
    """
    Cria nova reserva para o usuário autenticado.

    Regras:
        - Só permite reserva se NÃO há cópias disponíveis
        - Deve haver empréstimos ativos (para calcular expected_due_date)
        - Usuário não pode ter reserva duplicada para o mesmo título

    Raises:
        400: Há cópias disponíveis (deve emprestar diretamente)
        400: Reserva duplicada
        400: Não há empréstimos ativos
        404: Livro não encontrado
    """
    service = ReservationService(db)
    return await service.create_reservation(current_user, data.book_title_id)


@router.get(
    "",
    response_model=PaginatedResponse[ReservationDetail],
    summary="Listar reservas",
    description="Lista reservas com filtros. USER vê apenas as próprias; ADMIN vê todas.",
)
async def list_reservations(
    db: DbSession,
    current_user: CurrentUser,
    user_id: UUID | None = Query(None, description="Filtrar por usuário (apenas ADMIN)"),
    book_title_id: UUID | None = Query(None, description="Filtrar por título do livro"),
    status_filter: ReservationStatus | None = Query(
        None,
        alias="status",
        description="Filtro por status: ACTIVE, ON_HOLD, FULFILLED, EXPIRED, CANCELLED",
    ),
    page: int = Query(1, ge=1, description="Número da página"),
    page_size: int = Query(20, ge=1, le=100, description="Itens por página"),
) -> PaginatedResponse[ReservationDetail]:
    """
    Lista reservas com paginação e filtros.

    Autorização:
        - USER: vê apenas suas próprias reservas (ignora user_id)
        - ADMIN: pode filtrar por qualquer user_id

    Filtros:
        - status: ACTIVE, ON_HOLD, FULFILLED, EXPIRED, CANCELLED
        - book_title_id: ID do título do livro
        - user_id: ID do usuário (apenas admin)
    """
    service = ReservationService(db)

    # Autorização: USER só vê as próprias, ADMIN pode ver todas
    effective_user_id = user_id
    if current_user.role != UserRole.ADMIN:
        effective_user_id = current_user.id

    reservations, total = await service.reservation_repo.search(
        user_id=effective_user_id,
        book_title_id=book_title_id,
        status=status_filter,
        page=page,
        page_size=page_size,
    )

    # Converter para ReservationDetail com queue_position
    items = []
    for reservation in reservations:
        queue_position = None
        if reservation.status == ReservationStatus.ACTIVE:
            queue_position = await service._get_queue_position(reservation)
        items.append(
            ReservationDetail.from_reservation(reservation, queue_position)
        )

    return PaginatedResponse.create(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/my",
    response_model=list[ReservationDetail],
    summary="Minhas reservas ativas",
    description="Lista reservas ACTIVE ou ON_HOLD do usuário autenticado.",
)
async def my_active_reservations(
    db: DbSession,
    current_user: CurrentUser,
) -> list[ReservationDetail]:
    """
    Lista reservas pendentes do usuário autenticado.

    Atalho conveniente para ver reservas em andamento.
    Retorna apenas ACTIVE e ON_HOLD.
    """
    service = ReservationService(db)

    results = []
    for status_val in [ReservationStatus.ACTIVE, ReservationStatus.ON_HOLD]:
        reservations = await service.get_user_reservations(
            current_user.id,
            status_filter=status_val,
        )
        results.extend(reservations)

    return results


@router.get(
    "/{reservation_id}",
    response_model=ReservationDetail,
    summary="Detalhes da reserva",
    description="Retorna detalhes de uma reserva específica.",
)
async def get_reservation(
    reservation_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> ReservationDetail:
    """
    Retorna detalhes de uma reserva.

    Autorização:
        - USER: apenas suas próprias reservas
        - ADMIN: qualquer reserva

    Raises:
        403: Usuário não tem permissão para ver esta reserva
        404: Reserva não encontrada
    """
    service = ReservationService(db)
    reservation = await service.get_reservation_detail(reservation_id)

    # Verificar autorização
    if current_user.role != UserRole.ADMIN and reservation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para ver esta reserva",
        )

    return reservation


@router.patch(
    "/{reservation_id}/cancel",
    response_model=ReservationCancelResponse,
    summary="Cancelar reserva",
    description="Cancela uma reserva ACTIVE ou ON_HOLD.",
)
async def cancel_reservation(
    reservation_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> ReservationCancelResponse:
    """
    Cancela uma reserva.

    Regras:
        - Apenas reservas ACTIVE ou ON_HOLD podem ser canceladas
        - Se ON_HOLD, libera a cópia separada

    Autorização:
        - USER: apenas suas próprias reservas
        - ADMIN: qualquer reserva

    Raises:
        400: Reserva não pode ser cancelada (status final)
        403: Sem permissão
        404: Reserva não encontrada
    """
    service = ReservationService(db)
    is_admin = current_user.role == UserRole.ADMIN

    return await service.cancel_reservation(
        current_user,
        reservation_id,
        is_admin=is_admin,
    )

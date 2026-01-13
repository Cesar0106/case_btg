"""
Endpoints de Sistema (Admin).

Contratos:
    - POST /system/process-holds: Processa holds pendentes
    - POST /system/expire-holds: Expira holds vencidos

Autorização:
    - Todos os endpoints requerem ADMIN

Status codes:
    - 200: Sucesso
    - 401: Não autenticado
    - 403: Sem permissão (não é admin)
"""

from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.core.deps import DbSession, AdminUser
from app.schemas.reservation import HoldProcessResult, ExpireHoldsResult
from app.services.reservation import ReservationService

router = APIRouter(prefix="/system", tags=["System (Admin)"])


class ProcessHoldsResponse(BaseModel):
    """Resposta do processamento de holds."""

    results: list[HoldProcessResult]
    total_processed: int
    message: str


@router.post(
    "/process-holds",
    response_model=ProcessHoldsResponse,
    summary="Processar holds pendentes",
    description="Processa fila de reservas e atribui cópias disponíveis. **Requer ADMIN.**",
)
async def process_holds(
    db: DbSession,
    admin: AdminUser,
    book_title_id: UUID | None = Query(
        None,
        description="Processar apenas um título específico",
    ),
) -> ProcessHoldsResponse:
    """
    Processa holds para títulos com cópias disponíveis.

    Para cada título com reservas ACTIVE e cópias AVAILABLE:
        1. Seleciona a reserva mais antiga (FIFO)
        2. Marca uma cópia como ON_HOLD (24h)
        3. Marca a reserva como ON_HOLD

    Args:
        book_title_id: Processar apenas este título (opcional)

    Returns:
        Lista de holds criados
    """
    service = ReservationService(db)
    results = await service.process_holds(book_title_id)

    return ProcessHoldsResponse(
        results=results,
        total_processed=len(results),
        message=f"{len(results)} hold(s) processado(s)",
    )


@router.post(
    "/expire-holds",
    response_model=ExpireHoldsResult,
    summary="Expirar holds vencidos",
    description="Expira holds que passaram do prazo de 24h. **Requer ADMIN.**",
)
async def expire_holds(
    db: DbSession,
    admin: AdminUser,
) -> ExpireHoldsResult:
    """
    Expira holds que passaram do prazo.

    Para cada cópia ON_HOLD com hold_expires_at < now:
        1. Libera a cópia (status = AVAILABLE)
        2. Marca a reserva como EXPIRED
        3. Processa próxima reserva da fila (se houver)

    Returns:
        Contadores de holds expirados e novos holds processados
    """
    service = ReservationService(db)
    return await service.expire_holds()

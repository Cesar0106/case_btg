"""
Endpoints de Autores.

Contratos:
    - POST /authors: Cria autor (somente ADMIN)
    - GET /authors: Lista autores paginado (público autenticado)
    - GET /authors/{id}: Busca autor por ID (público autenticado)
    - PUT /authors/{id}: Atualiza autor (somente ADMIN)
    - DELETE /authors/{id}: Remove autor (somente ADMIN)

Status codes:
    - 200: Sucesso
    - 201: Criado com sucesso
    - 400: Erro de validação ou regra de negócio
    - 401: Não autenticado
    - 403: Sem permissão (não é admin)
    - 404: Autor não encontrado
"""

from uuid import UUID

from fastapi import APIRouter, Query, status

from app.core.deps import DbSession, CurrentUser, AdminUser
from app.schemas.author import AuthorCreate, AuthorRead, AuthorUpdate
from app.schemas.base import PaginatedResponse, MessageResponse
from app.services.author import AuthorService

router = APIRouter(prefix="/authors", tags=["Authors"])


@router.post(
    "",
    response_model=AuthorRead,
    status_code=status.HTTP_201_CREATED,
    summary="Criar autor",
    description="Cria um novo autor. **Requer role ADMIN.**",
)
async def create_author(
    data: AuthorCreate,
    db: DbSession,
    admin: AdminUser,
) -> AuthorRead:
    """
    Cria novo autor no sistema.

    Apenas administradores podem criar autores.
    O nome do autor não precisa ser único.
    """
    service = AuthorService(db)
    author = await service.create(data)
    return AuthorRead.model_validate(author)


@router.get(
    "",
    response_model=PaginatedResponse[AuthorRead],
    summary="Listar autores",
    description="Lista autores com paginação e filtro opcional por nome.",
)
async def list_authors(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1, description="Número da página"),
    page_size: int = Query(20, ge=1, le=100, description="Itens por página"),
    search: str | None = Query(None, description="Filtrar por nome"),
) -> PaginatedResponse[AuthorRead]:
    """
    Lista autores com paginação.

    Parâmetros de query:
        - page: Número da página (começa em 1)
        - page_size: Quantidade de itens por página (max 100)
        - search: Filtro parcial por nome (case insensitive)
    """
    service = AuthorService(db)
    authors, total = await service.list_paginated(page, page_size, search)

    return PaginatedResponse.create(
        items=[AuthorRead.model_validate(a) for a in authors],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{author_id}",
    response_model=AuthorRead,
    summary="Buscar autor",
    description="Busca autor por ID.",
)
async def get_author(
    author_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> AuthorRead:
    """
    Retorna dados de um autor específico.

    Raises:
        404: Autor não encontrado
    """
    service = AuthorService(db)
    author = await service.get_by_id(author_id)
    return AuthorRead.model_validate(author)


@router.put(
    "/{author_id}",
    response_model=AuthorRead,
    summary="Atualizar autor",
    description="Atualiza dados de um autor. **Requer role ADMIN.**",
)
async def update_author(
    author_id: UUID,
    data: AuthorUpdate,
    db: DbSession,
    admin: AdminUser,
) -> AuthorRead:
    """
    Atualiza nome do autor.

    Apenas administradores podem atualizar.

    Raises:
        404: Autor não encontrado
    """
    service = AuthorService(db)
    author = await service.update(author_id, data)
    return AuthorRead.model_validate(author)


@router.delete(
    "/{author_id}",
    response_model=MessageResponse,
    summary="Remover autor",
    description="Remove um autor. **Requer role ADMIN.** Não permite remover se houver livros.",
)
async def delete_author(
    author_id: UUID,
    db: DbSession,
    admin: AdminUser,
) -> MessageResponse:
    """
    Remove autor do sistema.

    Apenas administradores podem remover.
    Não é possível remover autor que possui livros cadastrados.

    Raises:
        400: Autor possui livros cadastrados
        404: Autor não encontrado
    """
    service = AuthorService(db)
    await service.delete(author_id)
    return MessageResponse(message="Autor removido com sucesso")

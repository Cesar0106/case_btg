"""
Endpoints de Livros (BookTitle e BookCopy).

Contratos:
    - POST /books: Cria título + N cópias (somente ADMIN)
    - GET /books: Lista títulos paginado com filtros
    - GET /books/{id}: Detalhes do título com contagem de cópias
    - PUT /books/{id}: Atualiza título (somente ADMIN)
    - DELETE /books/{id}: Remove título e cópias (somente ADMIN)
    - POST /books/{id}/copies: Adiciona cópias (somente ADMIN)
    - GET /books/{id}/copies: Lista cópias do título

Status codes:
    - 200: Sucesso
    - 201: Criado com sucesso
    - 400: Erro de validação ou regra de negócio
    - 401: Não autenticado
    - 403: Sem permissão (não é admin)
    - 404: Livro ou autor não encontrado
"""

from uuid import UUID

from fastapi import APIRouter, Query, status

from app.core.deps import DbSession, CurrentUser, AdminUser
from app.schemas.book import (
    BookTitleCreate,
    BookTitleRead,
    BookTitleUpdate,
    BookTitleDetail,
    BookCopyRead,
    BookAvailability,
)
from app.schemas.base import PaginatedResponse, MessageResponse
from app.services.book import BookService

router = APIRouter(prefix="/books", tags=["Books"])


# ==========================================
# Schema de resposta para criação
# ==========================================

from pydantic import BaseModel


class BookCreateResponse(BaseModel):
    """Resposta da criação de livro com cópias."""
    book: BookTitleRead
    copies_created: int

    model_config = {"from_attributes": True}


# ==========================================
# Endpoints de BookTitle
# ==========================================

@router.post(
    "",
    response_model=BookCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar livro com cópias",
    description="Cria um título de livro e gera N cópias. **Requer role ADMIN.**",
)
async def create_book(
    data: BookTitleCreate,
    db: DbSession,
    admin: AdminUser,
    quantity: int = Query(1, ge=1, le=100, description="Número de cópias a criar"),
) -> BookCreateResponse:
    """
    Cria novo título de livro e suas cópias físicas.

    Apenas administradores podem criar livros.

    Parâmetros:
        - data: Dados do título (title, author_id, published_year, pages)
        - quantity: Número de cópias a criar (padrão 1, max 100)

    Raises:
        404: Autor não encontrado
    """
    service = BookService(db)
    book, copies = await service.create_title_with_copies(data, quantity)

    return BookCreateResponse(
        book=BookTitleRead.model_validate(book),
        copies_created=len(copies),
    )


@router.get(
    "",
    response_model=PaginatedResponse[BookTitleRead],
    summary="Listar livros",
    description="Lista títulos de livros com paginação e filtros.",
)
async def list_books(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1, description="Número da página"),
    page_size: int = Query(20, ge=1, le=100, description="Itens por página"),
    title: str | None = Query(None, description="Filtrar por título"),
    author_id: UUID | None = Query(None, description="Filtrar por autor"),
) -> PaginatedResponse[BookTitleRead]:
    """
    Lista títulos de livros com paginação e filtros opcionais.

    Parâmetros de query:
        - page: Número da página (começa em 1)
        - page_size: Quantidade de itens por página (max 100)
        - title: Filtro parcial por título (case insensitive)
        - author_id: Filtro por ID do autor
    """
    service = BookService(db)
    books, total = await service.list_titles(
        title=title,
        author_id=author_id,
        page=page,
        page_size=page_size,
    )

    return PaginatedResponse.create(
        items=[BookTitleRead.model_validate(b) for b in books],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{book_id}",
    response_model=BookTitleDetail,
    summary="Detalhes do livro",
    description="Retorna detalhes do título incluindo contagem de cópias.",
)
async def get_book(
    book_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> BookTitleDetail:
    """
    Retorna detalhes de um título de livro.

    Inclui:
        - Dados do título e autor
        - Total de cópias
        - Cópias disponíveis

    Raises:
        404: Livro não encontrado
    """
    service = BookService(db)
    return await service.get_title_detail(book_id)


@router.put(
    "/{book_id}",
    response_model=BookTitleRead,
    summary="Atualizar livro",
    description="Atualiza dados de um título. **Requer role ADMIN.**",
)
async def update_book(
    book_id: UUID,
    data: BookTitleUpdate,
    db: DbSession,
    admin: AdminUser,
) -> BookTitleRead:
    """
    Atualiza dados do título.

    Apenas administradores podem atualizar.

    Raises:
        404: Livro ou autor não encontrado
    """
    service = BookService(db)
    book = await service.update_title(book_id, data)
    return BookTitleRead.model_validate(book)


@router.delete(
    "/{book_id}",
    response_model=MessageResponse,
    summary="Remover livro",
    description="Remove título e suas cópias. **Requer role ADMIN.** Não permite se houver cópias emprestadas.",
)
async def delete_book(
    book_id: UUID,
    db: DbSession,
    admin: AdminUser,
) -> MessageResponse:
    """
    Remove título e todas as suas cópias.

    Apenas administradores podem remover.
    Não é possível remover se houver cópias emprestadas.

    Raises:
        400: Existem cópias emprestadas
        404: Livro não encontrado
    """
    service = BookService(db)
    await service.delete_title(book_id)
    return MessageResponse(message="Livro removido com sucesso")


# ==========================================
# Availability Endpoint
# ==========================================

@router.get(
    "/{book_id}/availability",
    response_model=BookAvailability,
    summary="Verificar disponibilidade",
    description="Verifica se há cópias disponíveis para empréstimo.",
)
async def check_availability(
    book_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> BookAvailability:
    """
    Verifica disponibilidade de um título para empréstimo.

    Retorna:
        - available: True se há cópia disponível
        - reason: Motivo se não disponível ("All copies are loaned" ou "Copies on hold/reserved")
        - expected_due_date: Menor due_date dos empréstimos ativos (quando aplicável)
        - available_copies: Quantidade de cópias disponíveis
        - total_copies: Total de cópias do título

    Raises:
        404: Livro não encontrado
    """
    service = BookService(db)
    return await service.check_availability(book_id)


# ==========================================
# Endpoints de BookCopy
# ==========================================

@router.post(
    "/{book_id}/copies",
    response_model=list[BookCopyRead],
    status_code=status.HTTP_201_CREATED,
    summary="Adicionar cópias",
    description="Adiciona mais cópias a um título existente. **Requer role ADMIN.**",
)
async def add_copies(
    book_id: UUID,
    db: DbSession,
    admin: AdminUser,
    quantity: int = Query(1, ge=1, le=100, description="Número de cópias a adicionar"),
) -> list[BookCopyRead]:
    """
    Adiciona novas cópias a um título existente.

    Apenas administradores podem adicionar cópias.
    Todas as novas cópias são criadas com status AVAILABLE.

    Raises:
        404: Livro não encontrado
    """
    service = BookService(db)
    copies = await service.add_copies(book_id, quantity)
    return [BookCopyRead.model_validate(c) for c in copies]


@router.get(
    "/{book_id}/copies",
    response_model=list[BookCopyRead],
    summary="Listar cópias",
    description="Lista todas as cópias de um título.",
)
async def list_copies(
    book_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> list[BookCopyRead]:
    """
    Lista todas as cópias físicas de um título.

    Retorna status de cada cópia (AVAILABLE, LOANED, ON_HOLD).

    Raises:
        404: Livro não encontrado
    """
    service = BookService(db)
    copies = await service.list_copies(book_id)
    return [BookCopyRead.model_validate(c) for c in copies]

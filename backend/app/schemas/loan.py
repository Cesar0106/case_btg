"""
Schemas Pydantic para Loan (empréstimo).
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, computed_field

# Constantes de negócio
LOAN_PERIOD_DAYS = 14
FINE_PER_DAY = Decimal("2.00")
MAX_ACTIVE_LOANS = 3


class LoanCreate(BaseModel):
    """Schema para criar empréstimo."""

    book_title_id: UUID = Field(..., description="ID do título do livro")


class LoanRead(BaseModel):
    """Schema de leitura básico de empréstimo."""

    id: UUID
    user_id: UUID
    book_copy_id: UUID
    loaned_at: datetime
    due_date: datetime
    returned_at: datetime | None = None
    fine_amount_final: Decimal | None = None
    renewals_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LoanDetail(BaseModel):
    """
    Schema de leitura detalhado com cálculo de multa dinâmica.

    A multa dinâmica é calculada em tempo real para empréstimos
    ativos e atrasados, sem persistir no banco.
    """

    id: UUID
    user_id: UUID
    user_name: str | None = None
    user_email: str | None = None
    book_copy_id: UUID
    book_title: str | None = None
    book_title_id: UUID | None = None
    author_name: str | None = None
    loaned_at: datetime
    due_date: datetime
    returned_at: datetime | None = None
    fine_amount_final: Decimal | None = None
    renewals_count: int

    # Campos para cálculo dinâmico (preenchidos manualmente)
    _days_overdue: int = 0

    model_config = {"from_attributes": True}

    @computed_field
    @property
    def is_active(self) -> bool:
        """Retorna True se o empréstimo está ativo."""
        return self.returned_at is None

    @computed_field
    @property
    def is_overdue(self) -> bool:
        """Retorna True se o empréstimo está atrasado."""
        if self.returned_at is not None:
            return False
        return datetime.utcnow() > self.due_date.replace(tzinfo=None)

    @computed_field
    @property
    def days_overdue(self) -> int:
        """Dias em atraso (0 se não atrasado ou já devolvido)."""
        if self.returned_at is not None:
            return 0
        if not self.is_overdue:
            return 0
        delta = datetime.utcnow() - self.due_date.replace(tzinfo=None)
        return max(0, delta.days)

    @computed_field
    @property
    def current_fine(self) -> Decimal:
        """
        Multa atual calculada dinamicamente.

        Se já devolvido, retorna fine_amount_final.
        Se ativo e atrasado, calcula dias * R$2,00.
        Se ativo e não atrasado, retorna 0.
        """
        if self.returned_at is not None:
            return self.fine_amount_final or Decimal("0.00")
        return Decimal(self.days_overdue) * FINE_PER_DAY

    @classmethod
    def from_loan(cls, loan, user=None, book_copy=None) -> "LoanDetail":
        """
        Cria LoanDetail a partir de um objeto Loan com relações.

        Args:
            loan: Objeto Loan do SQLAlchemy
            user: Objeto User (opcional, usa loan.user se None)
            book_copy: Objeto BookCopy (opcional, usa loan.book_copy se None)
        """
        user = user or getattr(loan, "user", None)
        book_copy = book_copy or getattr(loan, "book_copy", None)
        book_title = getattr(book_copy, "book_title", None) if book_copy else None
        author = getattr(book_title, "author", None) if book_title else None

        return cls(
            id=loan.id,
            user_id=loan.user_id,
            user_name=user.name if user else None,
            user_email=user.email if user else None,
            book_copy_id=loan.book_copy_id,
            book_title=book_title.title if book_title else None,
            book_title_id=book_title.id if book_title else None,
            author_name=author.name if author else None,
            loaned_at=loan.loaned_at,
            due_date=loan.due_date,
            returned_at=loan.returned_at,
            fine_amount_final=loan.fine_amount_final,
            renewals_count=loan.renewals_count,
        )


class LoanReturn(BaseModel):
    """Schema de resposta para devolução de livro."""

    loan: LoanDetail
    fine_applied: Decimal = Field(..., description="Multa aplicada (pode ser 0)")
    message: str


class LoanRenew(BaseModel):
    """Schema de resposta para renovação de empréstimo."""

    loan: LoanDetail
    previous_due_date: datetime
    new_due_date: datetime
    message: str


class LoanListFilters(BaseModel):
    """Filtros para listagem de empréstimos."""

    user_id: UUID | None = None
    book_title_id: UUID | None = None
    status: str | None = Field(
        None,
        pattern="^(active|returned|overdue)$",
        description="Filtro por status: active, returned, overdue",
    )
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)

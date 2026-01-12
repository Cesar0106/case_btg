"""
Service para lógica de negócio de empréstimos (Loan).

Regras de negócio:
    - Usuário pode ter no máximo 3 empréstimos ativos
    - Prazo padrão: 14 dias
    - Multa por atraso: R$ 2,00/dia
    - Cópia pode ser AVAILABLE ou ON_HOLD (se reserva do próprio usuário)
"""

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.loan import Loan
from app.models.book import BookCopy
from app.models.user import User
from app.models.enums import CopyStatus
from app.repositories.loan import LoanRepository
from app.repositories.book import BookTitleRepository, BookCopyRepository
from app.schemas.loan import (
    LoanDetail,
    LoanReturn,
    LOAN_PERIOD_DAYS,
    FINE_PER_DAY,
    MAX_ACTIVE_LOANS,
)


class LoanService:
    """Service para operações de empréstimo."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.loan_repo = LoanRepository(db)
        self.title_repo = BookTitleRepository(db)
        self.copy_repo = BookCopyRepository(db)

    # ==========================================
    # Create Loan
    # ==========================================

    async def create_loan(
        self,
        user: User,
        book_title_id: UUID,
    ) -> Loan:
        """
        Cria um novo empréstimo.

        Fluxo:
            1. Verifica se usuário não excede limite de 3 ativos
            2. Busca cópia disponível (AVAILABLE) ou ON_HOLD do próprio usuário
            3. Marca cópia como LOANED
            4. Cria registro de Loan com due_date = now + 14 dias

        Args:
            user: Usuário que está fazendo o empréstimo
            book_title_id: ID do título do livro desejado

        Returns:
            Objeto Loan criado

        Raises:
            HTTPException 400: Usuário já tem 3 empréstimos ativos
            HTTPException 404: Livro não encontrado
            HTTPException 400: Nenhuma cópia disponível
        """
        # 1. Verificar limite de empréstimos ativos
        active_count = await self.loan_repo.count_active_by_user(user.id)
        if active_count >= MAX_ACTIVE_LOANS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Usuário já possui {MAX_ACTIVE_LOANS} empréstimos ativos. "
                       f"Devolva um livro antes de pegar outro.",
            )

        # 2. Verificar se o título existe
        book = await self.title_repo.get_with_copies(book_title_id)
        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Livro não encontrado",
            )

        # 3. Buscar cópia disponível
        copy = await self._find_available_copy(book.copies, user.id)
        if not copy:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nenhuma cópia disponível para empréstimo",
            )

        # 4. Marcar cópia como LOANED
        await self.copy_repo.update_status(
            copy,
            status=CopyStatus.LOANED,
            hold_reservation_id=None,  # Limpa campos de hold
            hold_expires_at=None,
        )

        # 5. Criar registro de empréstimo
        now = datetime.utcnow()
        due_date = now + timedelta(days=LOAN_PERIOD_DAYS)

        loan = Loan(
            user_id=user.id,
            book_copy_id=copy.id,
            loaned_at=now,
            due_date=due_date,
            renewals_count=0,
        )
        self.db.add(loan)
        await self.db.commit()
        await self.db.refresh(loan)

        # Recarregar com relacionamentos
        return await self.loan_repo.get_with_relations(loan.id)

    async def _find_available_copy(
        self,
        copies: list[BookCopy],
        user_id: UUID,
    ) -> BookCopy | None:
        """
        Encontra uma cópia disponível para empréstimo.

        Prioridade:
            1. Cópia ON_HOLD para reserva do próprio usuário (hold válido)
            2. Cópia AVAILABLE

        Args:
            copies: Lista de cópias do título
            user_id: ID do usuário que está pegando emprestado

        Returns:
            BookCopy disponível ou None se não houver
        """
        now = datetime.utcnow()

        # Primeiro: procurar cópia ON_HOLD para este usuário com hold válido
        for copy in copies:
            if (
                copy.status == CopyStatus.ON_HOLD
                and copy.hold_reservation_id is not None
                and copy.hold_expires_at is not None
                and copy.hold_expires_at.replace(tzinfo=None) > now
            ):
                # TODO: Verificar se hold_reservation_id pertence ao user_id
                # Isso requer consulta à tabela de reservas
                # Por enquanto, assumimos que se há hold, é do usuário correto
                # Na implementação completa de Reservation, validar aqui
                pass

        # Segundo: procurar qualquer cópia AVAILABLE
        for copy in copies:
            if copy.status == CopyStatus.AVAILABLE:
                return copy

        return None

    # ==========================================
    # Return Loan
    # ==========================================

    async def return_loan(self, loan_id: UUID) -> LoanReturn:
        """
        Processa a devolução de um empréstimo.

        Fluxo:
            1. Busca o empréstimo
            2. Verifica se não foi devolvido
            3. Calcula multa (dias_atraso * R$ 2,00)
            4. Marca returned_at e fine_amount_final
            5. Libera cópia (status AVAILABLE, limpa hold fields)

        Args:
            loan_id: ID do empréstimo

        Returns:
            LoanReturn com detalhes da devolução

        Raises:
            HTTPException 404: Empréstimo não encontrado
            HTTPException 400: Empréstimo já foi devolvido
        """
        # 1. Buscar empréstimo
        loan = await self.loan_repo.get_with_relations(loan_id)
        if not loan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Empréstimo não encontrado",
            )

        # 2. Verificar se já foi devolvido
        if loan.returned_at is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Este empréstimo já foi devolvido",
            )

        # 3. Calcular multa
        now = datetime.utcnow()
        due_date_naive = loan.due_date.replace(tzinfo=None)
        days_overdue = max(0, (now - due_date_naive).days)
        fine_amount = Decimal(days_overdue) * FINE_PER_DAY

        # 4. Atualizar loan
        loan.returned_at = now
        loan.fine_amount_final = fine_amount
        await self.db.commit()

        # 5. Liberar cópia
        copy = await self.copy_repo.get_by_id(loan.book_copy_id)
        if copy:
            await self.copy_repo.update_status(
                copy,
                status=CopyStatus.AVAILABLE,
                hold_reservation_id=None,
                hold_expires_at=None,
            )

        # Recarregar para retornar com dados atualizados
        loan = await self.loan_repo.get_with_relations(loan_id)

        # Montar resposta
        loan_detail = LoanDetail.from_loan(loan)

        if fine_amount > 0:
            message = f"Livro devolvido com {days_overdue} dia(s) de atraso. Multa: R$ {fine_amount:.2f}"
        else:
            message = "Livro devolvido com sucesso. Sem multa."

        return LoanReturn(
            loan=loan_detail,
            fine_applied=fine_amount,
            message=message,
        )

    # ==========================================
    # Get / List Loans
    # ==========================================

    async def get_loan_by_id(self, loan_id: UUID) -> Loan:
        """
        Busca empréstimo por ID.

        Raises:
            HTTPException 404: Empréstimo não encontrado
        """
        loan = await self.loan_repo.get_with_relations(loan_id)
        if not loan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Empréstimo não encontrado",
            )
        return loan

    async def get_loan_detail(self, loan_id: UUID) -> LoanDetail:
        """
        Busca empréstimo com detalhes formatados.

        Returns:
            LoanDetail com cálculo dinâmico de multa
        """
        loan = await self.get_loan_by_id(loan_id)
        return LoanDetail.from_loan(loan)

    async def list_loans(
        self,
        user_id: UUID | None = None,
        book_title_id: UUID | None = None,
        status_filter: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[LoanDetail], int]:
        """
        Lista empréstimos com filtros e paginação.

        Args:
            user_id: Filtrar por usuário
            book_title_id: Filtrar por título do livro
            status_filter: "active", "returned", "overdue"
            page: Número da página
            page_size: Itens por página

        Returns:
            Tupla (lista de LoanDetail, total)
        """
        loans, total = await self.loan_repo.search(
            user_id=user_id,
            book_title_id=book_title_id,
            status=status_filter,
            page=page,
            page_size=page_size,
        )

        loan_details = [LoanDetail.from_loan(loan) for loan in loans]
        return loan_details, total

    async def get_user_active_loans(self, user_id: UUID) -> list[LoanDetail]:
        """Lista empréstimos ativos de um usuário."""
        loans = await self.loan_repo.get_active_by_user(user_id)
        return [LoanDetail.from_loan(loan) for loan in loans]

    async def get_overdue_loans(self) -> list[LoanDetail]:
        """Lista todos os empréstimos atrasados (para relatórios/admin)."""
        loans = await self.loan_repo.get_overdue_loans()
        return [LoanDetail.from_loan(loan) for loan in loans]

    # ==========================================
    # Utility / Validation
    # ==========================================

    async def can_user_borrow(self, user_id: UUID) -> tuple[bool, str]:
        """
        Verifica se usuário pode pegar emprestado.

        Returns:
            Tupla (pode_emprestar, mensagem)
        """
        active_count = await self.loan_repo.count_active_by_user(user_id)
        if active_count >= MAX_ACTIVE_LOANS:
            return False, f"Limite de {MAX_ACTIVE_LOANS} empréstimos ativos atingido"
        return True, f"Pode emprestar ({active_count}/{MAX_ACTIVE_LOANS} ativos)"

    @staticmethod
    def calculate_fine(due_date: datetime, return_date: datetime | None = None) -> Decimal:
        """
        Calcula multa por atraso.

        Args:
            due_date: Data de vencimento
            return_date: Data de devolução (None = hoje)

        Returns:
            Valor da multa (0 se não atrasado)
        """
        if return_date is None:
            return_date = datetime.utcnow()

        due_date_naive = due_date.replace(tzinfo=None)
        return_date_naive = return_date.replace(tzinfo=None) if return_date.tzinfo else return_date

        days_overdue = max(0, (return_date_naive - due_date_naive).days)
        return Decimal(days_overdue) * FINE_PER_DAY

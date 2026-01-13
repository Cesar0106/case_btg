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
from app.models.enums import CopyStatus, ReservationStatus
from app.repositories.loan import LoanRepository
from app.repositories.book import BookTitleRepository, BookCopyRepository
from app.repositories.reservation import ReservationRepository
from app.schemas.loan import (
    LoanDetail,
    LoanReturn,
    LoanRenew,
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
        self.reservation_repo = ReservationRepository(db)

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

        # 3. Buscar cópia disponível (pode ser ON_HOLD para este usuário)
        copy, reservation_id = await self._find_available_copy(book.copies, user.id)
        if not copy:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nenhuma cópia disponível para empréstimo",
            )

        # 4. Se era ON_HOLD, marcar reserva como FULFILLED
        if reservation_id:
            reservation = await self.reservation_repo.get_by_id(reservation_id)
            if reservation:
                await self.reservation_repo.update_status(
                    reservation,
                    ReservationStatus.FULFILLED,
                )

        # 5. Marcar cópia como LOANED
        await self.copy_repo.update_status(
            copy,
            status=CopyStatus.LOANED,
            hold_reservation_id=None,  # Limpa campos de hold
            hold_expires_at=None,
        )

        # 6. Criar registro de empréstimo
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
    ) -> tuple[BookCopy | None, UUID | None]:
        """
        Encontra uma cópia disponível para empréstimo.

        Prioridade:
            1. Cópia ON_HOLD para reserva do próprio usuário (hold válido)
            2. Cópia AVAILABLE

        Args:
            copies: Lista de cópias do título
            user_id: ID do usuário que está pegando emprestado

        Returns:
            Tupla (BookCopy disponível ou None, reservation_id se ON_HOLD)
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
                # Verificar se a reserva pertence ao usuário
                reservation = await self.reservation_repo.get_by_id(
                    copy.hold_reservation_id
                )
                if reservation and reservation.user_id == user_id:
                    return copy, reservation.id

        # Segundo: procurar qualquer cópia AVAILABLE
        for copy in copies:
            if copy.status == CopyStatus.AVAILABLE:
                return copy, None

        return None, None

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
    # Renew Loan
    # ==========================================

    async def renew_loan(self, loan_id: UUID, user_id: UUID) -> LoanRenew:
        """
        Renova um empréstimo.

        Regras:
            1. Empréstimo deve estar ATIVO (não devolvido)
            2. renewals_count < 1 (só pode renovar 1 vez)
            3. Não pode estar atrasado (now <= due_date)
            4. Não pode existir reserva ACTIVE/ON_HOLD para o book_title

        Ação:
            - due_date += 14 dias
            - renewals_count += 1

        Args:
            loan_id: ID do empréstimo
            user_id: ID do usuário solicitando (para validar propriedade)

        Returns:
            LoanRenew com detalhes da renovação

        Raises:
            HTTPException 404: Empréstimo não encontrado
            HTTPException 403: Empréstimo não pertence ao usuário
            HTTPException 400: Empréstimo já devolvido
            HTTPException 400: Já renovou o máximo permitido
            HTTPException 400: Empréstimo está atrasado
            HTTPException 400: Há reservas pendentes para este título
        """
        # 1. Buscar empréstimo
        loan = await self.loan_repo.get_with_relations(loan_id)
        if not loan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Empréstimo não encontrado",
            )

        # 2. Verificar propriedade
        if loan.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Este empréstimo não pertence a você",
            )

        # 3. Verificar se está ativo (não devolvido)
        if loan.returned_at is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Não é possível renovar um empréstimo já devolvido",
            )

        # 4. Verificar limite de renovações
        if loan.renewals_count >= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Limite de renovações atingido (máximo: 1)",
            )

        # 5. Verificar se está atrasado
        now = datetime.utcnow()
        due_date_naive = loan.due_date.replace(tzinfo=None)
        if now > due_date_naive:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Não é possível renovar um empréstimo atrasado",
            )

        # 6. Verificar se há reservas ACTIVE ou ON_HOLD para o título
        book_copy = loan.book_copy
        book_title_id = book_copy.book_title_id if book_copy else None

        if book_title_id:
            active_reservation = await self.reservation_repo.get_active_by_user_and_title(
                user_id=user_id,  # Dummy, vamos buscar qualquer reserva ativa
                book_title_id=book_title_id,
            )
            # Na verdade, precisamos verificar se QUALQUER usuário tem reserva
            # Vamos buscar a primeira reserva ativa para este título
            first_active = await self.reservation_repo.get_first_active_by_title(
                book_title_id
            )
            if first_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Não é possível renovar: há reservas pendentes para este título",
                )

            # Verificar também reservas ON_HOLD
            reservations, _ = await self.reservation_repo.search(
                book_title_id=book_title_id,
                status=ReservationStatus.ON_HOLD,
                page=1,
                page_size=1,
            )
            if reservations:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Não é possível renovar: há reservas pendentes para este título",
                )

        # 7. Aplicar renovação
        previous_due_date = loan.due_date
        new_due_date = due_date_naive + timedelta(days=LOAN_PERIOD_DAYS)

        loan.due_date = new_due_date
        loan.renewals_count += 1
        await self.db.commit()

        # 8. Recarregar e retornar
        loan = await self.loan_repo.get_with_relations(loan_id)
        loan_detail = LoanDetail.from_loan(loan)

        return LoanRenew(
            loan=loan_detail,
            previous_due_date=previous_due_date,
            new_due_date=new_due_date,
            message=f"Empréstimo renovado com sucesso. Nova data de devolução: {new_due_date.strftime('%d/%m/%Y')}",
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

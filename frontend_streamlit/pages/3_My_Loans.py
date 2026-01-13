"""
My Loans page.

Displays the user's active and historical loans with actions.
"""

import streamlit as st

from utils.api_client import APIError, get_api_client
from utils.auth import require_auth
from utils.formatters import (
    calculate_days_until,
    format_currency,
    format_date,
    format_datetime,
    format_days_remaining,
    format_status,
)
from utils.state import init_session_state

init_session_state()

st.set_page_config(page_title="Meus Empréstimos - Library", page_icon="📗", layout="wide")

st.title("📗 Meus Empréstimos")

if not require_auth():
    st.stop()

api = get_api_client()


def load_my_loans() -> list:
    """Load current user's loans."""
    try:
        response = api.get("loans/my")
        if isinstance(response, list):
            return response
        return response.get("items", [])
    except APIError as e:
        st.error(f"Erro ao carregar empréstimos: {e.message}")
        return []


def return_loan(loan_id: str) -> tuple[bool, str, dict | None]:
    """Return a loan."""
    try:
        response = api.patch(f"loans/{loan_id}/return")
        return True, "Livro devolvido com sucesso!", response
    except APIError as e:
        return False, e.message, None


def renew_loan(loan_id: str) -> tuple[bool, str, dict | None]:
    """Renew a loan."""
    try:
        response = api.patch(f"loans/{loan_id}/renew")
        return True, "Empréstimo renovado com sucesso!", response
    except APIError as e:
        return False, e.message, None


if st.button("🔄 Atualizar"):
    st.rerun()

loans = load_my_loans()

if not loans:
    st.info("Você não possui empréstimos.")
    st.page_link("pages/2_Catalog.py", label="📚 Ir para o Catálogo", icon="📚")
    st.stop()

active_loans = [l for l in loans if not l.get("returned_at")]
returned_loans = [l for l in loans if l.get("returned_at")]

tab_active, tab_history = st.tabs([f"Ativos ({len(active_loans)})", f"Histórico ({len(returned_loans)})"])

with tab_active:
    if not active_loans:
        st.info("Nenhum empréstimo ativo.")
    else:
        for loan in active_loans:
            loan_id = loan.get("id")
            book_title = loan.get("book_title", "Título desconhecido")
            due_date = loan.get("due_date")
            days_remaining = calculate_days_until(due_date)
            renewals = loan.get("renewals_count", 0)

            is_overdue = days_remaining is not None and days_remaining < 0

            with st.container(border=True):
                col1, col2, col3 = st.columns([2, 1, 1])

                with col1:
                    st.subheader(book_title)

                    loaned_at = format_date(loan.get("loaned_at"))
                    st.caption(f"Emprestado em: {loaned_at}")

                with col2:
                    if is_overdue:
                        st.error(f"⚠️ {format_days_remaining(days_remaining)}")
                    else:
                        st.info(f"📅 Devolução: {format_date(due_date)}")
                        if days_remaining is not None:
                            st.caption(format_days_remaining(days_remaining))

                    st.caption(f"Renovações: {renewals}/2")

                with col3:
                    if st.button("📘 Devolver", key=f"return_{loan_id}", use_container_width=True):
                        success, message, response = return_loan(loan_id)
                        if success:
                            st.success(message)

                            fine_info = response.get("fine") if response else None
                            if fine_info:
                                fine_amount = fine_info.get("amount", 0)
                                days_overdue = fine_info.get("days_overdue", 0)
                                st.warning(
                                    f"Multa por atraso: {format_currency(fine_amount)} "
                                    f"({days_overdue} dias)"
                                )

                            st.rerun()
                        else:
                            st.error(message)

                    can_renew = renewals < 2 and not is_overdue
                    if st.button(
                        "🔄 Renovar",
                        key=f"renew_{loan_id}",
                        use_container_width=True,
                        disabled=not can_renew,
                    ):
                        success, message, response = renew_loan(loan_id)
                        if success:
                            new_due = response.get("new_due_date") if response else None
                            st.success(f"{message} Nova data: {format_date(new_due)}")
                            st.rerun()
                        else:
                            st.error(message)

with tab_history:
    if not returned_loans:
        st.info("Nenhum empréstimo devolvido.")
    else:
        for loan in returned_loans:
            book_title = loan.get("book_title", "Título desconhecido")
            returned_at = loan.get("returned_at")
            fine = loan.get("fine_amount_final") or loan.get("fine_amount")

            with st.container(border=True):
                col1, col2, col3 = st.columns([2, 1, 1])

                with col1:
                    st.markdown(f"**{book_title}**")
                    st.caption(f"Emprestado em: {format_date(loan.get('loaned_at'))}")

                with col2:
                    st.caption(f"Devolvido em: {format_date(returned_at)}")

                with col3:
                    label, color = format_status("RETURNED", "loan")
                    st.markdown(f":{color}[{label}]")

                    if fine and float(fine) > 0:
                        st.caption(f"Multa: {format_currency(fine)}")

"""
Admin Users page.

User management for administrators.
"""

import streamlit as st

from utils.api_client import APIError, get_api_client
from utils.auth import require_admin
from utils.formatters import format_date, format_datetime, format_currency, format_status
from utils.state import init_session_state

init_session_state()

st.set_page_config(page_title="Usuários - Library", page_icon="👥", layout="wide")

st.title("👥 Gestão de Usuários")

if not require_admin():
    st.stop()

api = get_api_client()


def load_users(page: int = 1, page_size: int = 20, role: str | None = None) -> tuple[list, int]:
    """Load users with pagination."""
    try:
        params = {"page": page, "page_size": page_size}
        if role:
            params["role"] = role

        response = api.get("users", params=params)
        items = response.get("items", [])
        total = response.get("total", 0)
        return items, total
    except APIError as e:
        st.error(f"Erro ao carregar usuários: {e.message}")
        return [], 0


def load_user(user_id: str) -> dict | None:
    """Load a specific user."""
    try:
        return api.get(f"users/{user_id}")
    except APIError as e:
        st.error(f"Erro ao carregar usuário: {e.message}")
        return None


def load_user_loans(user_id: str, status_filter: str | None = None) -> list:
    """Load loans for a specific user."""
    try:
        params = {}
        if status_filter:
            params["status"] = status_filter

        response = api.get(f"users/{user_id}/loans", params=params)
        if isinstance(response, list):
            return response
        return response.get("items", [])
    except APIError as e:
        st.error(f"Erro ao carregar empréstimos: {e.message}")
        return []


col_filter, col_search = st.columns([1, 2])

with col_filter:
    role_filter = st.selectbox(
        "Filtrar por role",
        options=["Todos", "USER", "ADMIN"],
        index=0,
    )

with col_search:
    user_id_search = st.text_input(
        "Buscar por ID do usuário",
        placeholder="Cole o UUID do usuário aqui...",
    )

if "users_page" not in st.session_state:
    st.session_state.users_page = 1

if user_id_search:
    st.subheader("Resultado da Busca")

    user = load_user(user_id_search.strip())

    if user:
        with st.container(border=True):
            col1, col2 = st.columns([2, 1])

            with col1:
                st.markdown(f"### {user.get('name', 'N/A')}")
                st.markdown(f"**Email:** {user.get('email', 'N/A')}")
                st.markdown(f"**Role:** {user.get('role', 'N/A')}")
                st.markdown(f"**ID:** `{user.get('id')}`")

            with col2:
                active_loans = user.get("active_loans_count", 0)
                total_loans = user.get("total_loans_count", 0)

                st.metric("Empréstimos Ativos", active_loans)
                st.metric("Total de Empréstimos", total_loans)

        st.divider()
        st.subheader("Empréstimos do Usuário")

        tab_active, tab_all = st.tabs(["Ativos", "Todos"])

        with tab_active:
            loans = load_user_loans(user_id_search.strip(), "active")
            if loans:
                for loan in loans:
                    with st.container(border=True):
                        col1, col2 = st.columns([2, 1])
                        with col1:
                            st.markdown(f"**{loan.get('book_title', 'N/A')}**")
                            st.caption(f"Emprestado em: {format_date(loan.get('loaned_at'))}")
                        with col2:
                            st.markdown(f"Devolução: {format_date(loan.get('due_date'))}")
                            if loan.get("is_overdue"):
                                st.error("Atrasado!")
            else:
                st.info("Nenhum empréstimo ativo.")

        with tab_all:
            loans = load_user_loans(user_id_search.strip())
            if loans:
                for loan in loans:
                    with st.container(border=True):
                        col1, col2, col3 = st.columns([2, 1, 1])
                        with col1:
                            st.markdown(f"**{loan.get('book_title', 'N/A')}**")
                        with col2:
                            st.caption(f"Emprestado: {format_date(loan.get('loaned_at'))}")
                            if loan.get("returned_at"):
                                st.caption(f"Devolvido: {format_date(loan.get('returned_at'))}")
                        with col3:
                            status = loan.get("status", "ACTIVE")
                            label, color = format_status(status, "loan")
                            st.markdown(f":{color}[{label}]")

                            fine = loan.get("fine_amount_final")
                            if fine and float(fine) > 0:
                                st.caption(f"Multa: {format_currency(fine)}")
            else:
                st.info("Nenhum empréstimo encontrado.")
    else:
        st.warning("Usuário não encontrado.")

else:
    role = role_filter if role_filter != "Todos" else None
    users, total = load_users(
        page=st.session_state.users_page,
        page_size=20,
        role=role,
    )

    if users:
        st.caption(f"Total: {total} usuários")

        for user in users:
            with st.container(border=True):
                col1, col2, col3, col4 = st.columns([2, 1, 1, 1])

                with col1:
                    st.markdown(f"**{user.get('name', 'N/A')}**")
                    st.caption(user.get("email", "N/A"))

                with col2:
                    role = user.get("role", "USER")
                    if role == "ADMIN":
                        st.markdown(":red[ADMIN]")
                    else:
                        st.markdown(":blue[USER]")

                with col3:
                    active = user.get("active_loans_count", 0)
                    total_u = user.get("total_loans_count", 0)
                    st.caption(f"Ativos: {active}")
                    st.caption(f"Total: {total_u}")

                with col4:
                    user_id = user.get("id")
                    if st.button("Ver", key=f"view_{user_id}"):
                        st.session_state.view_user_id = user_id
                        st.rerun()

        total_pages = max(1, (total + 19) // 20)

        col_prev, col_info, col_next = st.columns([1, 2, 1])

        with col_prev:
            if st.button("⬅️ Anterior", disabled=st.session_state.users_page <= 1):
                st.session_state.users_page -= 1
                st.rerun()

        with col_info:
            st.caption(f"Página {st.session_state.users_page} de {total_pages}")

        with col_next:
            if st.button("Próxima ➡️", disabled=st.session_state.users_page >= total_pages):
                st.session_state.users_page += 1
                st.rerun()

    else:
        st.info("Nenhum usuário encontrado.")

if "view_user_id" in st.session_state and st.session_state.view_user_id:
    st.divider()
    st.subheader("Detalhes do Usuário")

    user = load_user(st.session_state.view_user_id)

    if user:
        with st.container(border=True):
            col1, col2, col3 = st.columns([2, 1, 1])

            with col1:
                st.markdown(f"### {user.get('name', 'N/A')}")
                st.markdown(f"**Email:** {user.get('email', 'N/A')}")
                st.markdown(f"**Role:** {user.get('role', 'N/A')}")
                st.code(user.get("id"), language=None)

            with col2:
                st.metric("Empréstimos Ativos", user.get("active_loans_count", 0))
                st.metric("Total", user.get("total_loans_count", 0))

            with col3:
                if st.button("✖️ Fechar"):
                    st.session_state.view_user_id = None
                    st.rerun()

        loans = load_user_loans(st.session_state.view_user_id)
        if loans:
            st.caption(f"Últimos empréstimos ({len(loans)})")
            for loan in loans[:5]:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.caption(f"• {loan.get('book_title', 'N/A')}")
                with col2:
                    status = loan.get("status", "ACTIVE")
                    label, _ = format_status(status, "loan")
                    st.caption(label)

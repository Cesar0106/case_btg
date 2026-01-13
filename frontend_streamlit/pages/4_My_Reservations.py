"""
My Reservations page.

Displays the user's reservations with status and actions.
"""

import streamlit as st

from utils.api_client import APIError, get_api_client
from utils.auth import require_auth
from utils.formatters import (
    calculate_days_until,
    format_datetime,
    format_status,
)
from utils.state import init_session_state

init_session_state()

st.set_page_config(page_title="Minhas Reservas - Library", page_icon="📋", layout="wide")

st.title("📋 Minhas Reservas")

if not require_auth():
    st.stop()

api = get_api_client()


def load_my_reservations() -> list:
    """Load current user's reservations."""
    try:
        response = api.get("reservations/my")
        if isinstance(response, list):
            return response
        return response.get("items", [])
    except APIError as e:
        st.error(f"Erro ao carregar reservas: {e.message}")
        return []


def cancel_reservation(reservation_id: str) -> tuple[bool, str]:
    """Cancel a reservation."""
    try:
        api.patch(f"reservations/{reservation_id}/cancel")
        return True, "Reserva cancelada com sucesso!"
    except APIError as e:
        return False, e.message


if st.button("🔄 Atualizar"):
    st.rerun()

reservations = load_my_reservations()

if not reservations:
    st.info("Você não possui reservas.")
    st.page_link("pages/2_Catalog.py", label="📚 Ir para o Catálogo", icon="📚")
    st.stop()

active_reservations = [
    r for r in reservations if r.get("status") in ("ACTIVE", "ON_HOLD")
]
other_reservations = [
    r for r in reservations if r.get("status") not in ("ACTIVE", "ON_HOLD")
]

tab_active, tab_history = st.tabs([
    f"Ativas ({len(active_reservations)})",
    f"Histórico ({len(other_reservations)})",
])

with tab_active:
    if not active_reservations:
        st.info("Nenhuma reserva ativa.")
    else:
        for reservation in active_reservations:
            res_id = reservation.get("id")
            book_title = reservation.get("book_title", "Título desconhecido")
            status = reservation.get("status")
            queue_position = reservation.get("queue_position")
            hold_expires_at = reservation.get("hold_expires_at")
            created_at = reservation.get("created_at")

            label, color = format_status(status, "reservation")

            with st.container(border=True):
                col1, col2, col3 = st.columns([2, 1, 1])

                with col1:
                    st.subheader(book_title)
                    st.caption(f"Criada em: {format_datetime(created_at)}")

                with col2:
                    if status == "ON_HOLD":
                        st.warning(f"🔔 **{label}**")
                        st.markdown(f"⏰ Expira em: **{format_datetime(hold_expires_at)}**")

                        hours_remaining = calculate_days_until(hold_expires_at)
                        if hours_remaining is not None:
                            if hours_remaining < 0:
                                st.error("⚠️ Hold expirado!")
                            else:
                                st.caption("Retire o livro antes do prazo!")
                    else:
                        st.info(f"⏳ **{label}**")
                        if queue_position:
                            st.caption(f"Posição na fila: {queue_position}")

                with col3:
                    can_cancel = status in ("ACTIVE", "ON_HOLD")
                    if st.button(
                        "❌ Cancelar",
                        key=f"cancel_{res_id}",
                        use_container_width=True,
                        disabled=not can_cancel,
                    ):
                        success, message = cancel_reservation(res_id)
                        if success:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)

                    if status == "ON_HOLD":
                        st.page_link(
                            "pages/2_Catalog.py",
                            label="📗 Emprestar",
                            icon="📗",
                        )

with tab_history:
    if not other_reservations:
        st.info("Nenhuma reserva no histórico.")
    else:
        for reservation in other_reservations:
            book_title = reservation.get("book_title", "Título desconhecido")
            status = reservation.get("status")
            created_at = reservation.get("created_at")

            label, color = format_status(status, "reservation")

            with st.container(border=True):
                col1, col2, col3 = st.columns([2, 1, 1])

                with col1:
                    st.markdown(f"**{book_title}**")
                    st.caption(f"Criada em: {format_datetime(created_at)}")

                with col2:
                    pass

                with col3:
                    st.markdown(f":{color}[{label}]")

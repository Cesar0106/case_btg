"""
Library API - Frontend Streamlit

Main entry point for the Streamlit application.
Provides a demo interface for testing the Library API.
"""

import streamlit as st

from utils.state import (
    init_session_state,
    is_authenticated,
    is_admin,
    get_user_name,
    get_user_role,
)
from utils.auth import logout_user

init_session_state()

st.set_page_config(
    page_title="Library API",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

with st.sidebar:
    st.title("📚 Library API")
    st.caption("Demo Frontend")

    st.divider()

    st.subheader("⚙️ Configuração")
    base_url = st.text_input(
        "URL do Backend",
        value=st.session_state.get("base_url", "http://localhost:8000"),
        help="URL base da API (sem /api/v1)",
    )
    if base_url != st.session_state.base_url:
        st.session_state.base_url = base_url

    st.divider()

    if is_authenticated():
        st.success(f"👤 {get_user_name()}")
        st.caption(f"Role: {get_user_role()}")

        if st.button("🚪 Sair", use_container_width=True):
            logout_user()
            st.rerun()
    else:
        st.warning("Não autenticado")
        st.page_link("pages/1_Login.py", label="🔐 Fazer Login", icon="🔐")

    st.divider()

    st.subheader("📖 Navegação")

    st.page_link("pages/1_Login.py", label="Login / Signup", icon="🔐")

    if is_authenticated():
        st.page_link("pages/2_Catalog.py", label="Catálogo", icon="📚")
        st.page_link("pages/3_My_Loans.py", label="Meus Empréstimos", icon="📗")
        st.page_link("pages/4_My_Reservations.py", label="Minhas Reservas", icon="📋")

        if is_admin():
            st.divider()
            st.caption("Administração")
            st.page_link("pages/5_Admin.py", label="Gerenciar", icon="⚙️")
            st.page_link("pages/6_Admin_Users.py", label="Usuários", icon="👥")

st.title("📚 Bem-vindo à Library API")

st.markdown("""
Este é o frontend de demonstração para a **Library API**, desenvolvido como
parte de um case técnico.

### Funcionalidades

#### Para Usuários
- 📚 **Catálogo**: Navegue pelos livros disponíveis
- 📗 **Empréstimos**: Empreste e devolva livros
- 📋 **Reservas**: Reserve livros quando não houver cópias disponíveis
- 🔄 **Renovações**: Renove seus empréstimos (máximo 2 vezes)

#### Para Administradores
- 📝 **Autores**: Cadastre novos autores
- 📚 **Livros**: Cadastre livros e adicione cópias
- ⚙️ **Sistema**: Processe holds e expire reservas
- 👥 **Usuários**: Gerencie usuários e visualize empréstimos
- ⚠️ **Atrasados**: Monitore empréstimos em atraso

### Começando

1. Faça login com suas credenciais ou crie uma nova conta
2. Navegue pelo catálogo de livros
3. Empreste ou reserve os livros desejados

""")

if not is_authenticated():
    st.info("👆 Faça login para começar a usar o sistema.")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Credenciais de Admin (teste):**")
        st.code("Email: admin@library.local\nSenha: Admin123!")

    with col2:
        st.page_link(
            "pages/1_Login.py",
            label="Ir para Login",
            icon="🔐",
            use_container_width=True,
        )

else:
    st.success(f"Olá, **{get_user_name()}**! Escolha uma opção no menu lateral.")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.page_link(
            "pages/2_Catalog.py",
            label="📚 Ver Catálogo",
            use_container_width=True,
        )

    with col2:
        st.page_link(
            "pages/3_My_Loans.py",
            label="📗 Meus Empréstimos",
            use_container_width=True,
        )

    with col3:
        st.page_link(
            "pages/4_My_Reservations.py",
            label="📋 Minhas Reservas",
            use_container_width=True,
        )

st.divider()

st.caption("Library API Demo - Case Técnico BTG")

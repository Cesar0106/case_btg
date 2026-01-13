"""
Login and Signup page.

Allows users to authenticate or create new accounts.
"""

import streamlit as st

from utils.auth import login_user, logout_user, signup_user
from utils.state import init_session_state, is_authenticated, get_user_name, get_user_role

init_session_state()

st.set_page_config(page_title="Login - Library", page_icon="🔐", layout="centered")

st.title("🔐 Autenticação")

if is_authenticated():
    st.success(f"Você está logado como **{get_user_name()}** ({get_user_role()})")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("📚 Ir para Catálogo", use_container_width=True):
            st.switch_page("pages/2_Catalog.py")
    with col2:
        if st.button("🚪 Sair", use_container_width=True, type="secondary"):
            logout_user()
            st.rerun()

else:
    tab_login, tab_signup = st.tabs(["Login", "Criar Conta"])

    with tab_login:
        st.subheader("Entrar na sua conta")

        with st.form("login_form"):
            email = st.text_input("Email", placeholder="seu@email.com")
            password = st.text_input("Senha", type="password", placeholder="••••••••")

            submitted = st.form_submit_button("Entrar", use_container_width=True)

            if submitted:
                if not email:
                    st.error("Informe o email")
                elif not password:
                    st.error("Informe a senha")
                else:
                    with st.spinner("Autenticando..."):
                        success, message = login_user(email, password)

                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)

        st.divider()
        st.caption("Credenciais de teste:")
        st.code("Admin: admin@library.local / Admin123!")

    with tab_signup:
        st.subheader("Criar nova conta")

        with st.form("signup_form"):
            name = st.text_input("Nome completo", placeholder="João Silva")
            email = st.text_input("Email", placeholder="seu@email.com", key="signup_email")
            password = st.text_input(
                "Senha",
                type="password",
                placeholder="Mínimo 8 caracteres",
                key="signup_password",
            )
            password_confirm = st.text_input(
                "Confirmar senha",
                type="password",
                placeholder="Repita a senha",
            )

            submitted = st.form_submit_button("Criar conta", use_container_width=True)

            if submitted:
                if not name or len(name) < 2:
                    st.error("Nome deve ter pelo menos 2 caracteres")
                elif not email or "@" not in email:
                    st.error("Email inválido")
                elif not password or len(password) < 8:
                    st.error("Senha deve ter pelo menos 8 caracteres")
                elif password != password_confirm:
                    st.error("As senhas não coincidem")
                else:
                    with st.spinner("Criando conta..."):
                        success, message = signup_user(name, email, password)

                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)

        st.info("A senha deve conter letras maiúsculas, minúsculas, números e caracteres especiais.")

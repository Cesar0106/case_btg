"""
Authentication utilities for the Streamlit frontend.

Provides login, signup, and access control functions.
"""

import streamlit as st

from .api_client import APIError, get_api_client
from .state import clear_session, is_admin, is_authenticated, set_user_session


def login_user(email: str, password: str) -> tuple[bool, str]:
    """
    Authenticate user with email and password.

    Args:
        email: User email
        password: User password

    Returns:
        Tuple of (success: bool, message: str)
    """
    if not email or not password:
        return False, "Email e senha são obrigatórios"

    try:
        api = get_api_client()

        response = api.post(
            "auth/login",
            json={"email": email, "password": password},
            include_auth=False,
        )

        token = response.get("token", {}).get("access_token")
        if not token:
            return False, "Resposta inválida do servidor"

        st.session_state.token = token

        user_data = api.get("auth/me")
        set_user_session(token, user_data)

        return True, "Login realizado com sucesso"

    except APIError as e:
        return False, e.message
    except Exception as e:
        return False, f"Erro ao fazer login: {str(e)}"


def signup_user(name: str, email: str, password: str) -> tuple[bool, str]:
    """
    Register a new user.

    Args:
        name: User name
        email: User email
        password: User password

    Returns:
        Tuple of (success: bool, message: str)
    """
    if not name or len(name) < 2:
        return False, "Nome deve ter pelo menos 2 caracteres"
    if not email or "@" not in email:
        return False, "Email inválido"
    if not password or len(password) < 8:
        return False, "Senha deve ter pelo menos 8 caracteres"

    try:
        api = get_api_client()

        response = api.post(
            "auth/signup",
            json={"name": name, "email": email, "password": password},
            include_auth=False,
        )

        token = response.get("token", {}).get("access_token")
        if token:
            user_data = response.get("user", {})
            set_user_session(token, user_data)
            return True, "Conta criada com sucesso"

        return True, "Conta criada. Faça login para continuar."

    except APIError as e:
        return False, e.message
    except Exception as e:
        return False, f"Erro ao criar conta: {str(e)}"


def logout_user() -> None:
    """Log out the current user."""
    clear_session()


def require_auth() -> bool:
    """
    Check if user is authenticated.

    Displays warning and returns False if not authenticated.

    Returns:
        True if authenticated, False otherwise
    """
    if not is_authenticated():
        st.warning("Você precisa fazer login para acessar esta página.")
        st.page_link("pages/1_Login.py", label="Ir para Login", icon="🔐")
        return False
    return True


def require_admin() -> bool:
    """
    Check if user is an admin.

    Displays warning and returns False if not admin.

    Returns:
        True if admin, False otherwise
    """
    if not require_auth():
        return False

    if not is_admin():
        st.error("Acesso restrito. Esta página é apenas para administradores.")
        return False

    return True

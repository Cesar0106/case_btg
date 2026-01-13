"""
Session state management utilities.

Provides helpers for managing authentication state and user information
in Streamlit's session_state.
"""

import streamlit as st


def init_session_state() -> None:
    """
    Initialize session state with default values.

    Should be called at the start of the application.
    """
    defaults = {
        "token": None,
        "user_id": None,
        "email": None,
        "name": None,
        "role": None,
        "base_url": "http://localhost:8000",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def clear_session() -> None:
    """Clear all authentication-related session state."""
    st.session_state.token = None
    st.session_state.user_id = None
    st.session_state.email = None
    st.session_state.name = None
    st.session_state.role = None


def set_user_session(token: str, user_data: dict) -> None:
    """
    Set user session after successful login.

    Args:
        token: JWT access token
        user_data: User data from /auth/me endpoint
    """
    st.session_state.token = token
    st.session_state.user_id = user_data.get("id")
    st.session_state.email = user_data.get("email")
    st.session_state.name = user_data.get("name")
    st.session_state.role = user_data.get("role")


def get_token() -> str | None:
    """Get the current authentication token."""
    return st.session_state.get("token")


def get_user_id() -> str | None:
    """Get the current user ID."""
    return st.session_state.get("user_id")


def get_user_role() -> str | None:
    """Get the current user role."""
    return st.session_state.get("role")


def get_user_name() -> str | None:
    """Get the current user name."""
    return st.session_state.get("name")


def get_user_email() -> str | None:
    """Get the current user email."""
    return st.session_state.get("email")


def is_authenticated() -> bool:
    """Check if the user is authenticated."""
    return bool(st.session_state.get("token"))


def is_admin() -> bool:
    """Check if the current user is an admin."""
    return st.session_state.get("role") == "ADMIN"

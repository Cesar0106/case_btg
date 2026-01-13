"""
Formatting utilities for display.

Provides consistent formatting for dates, currency, and status values.
"""

from datetime import datetime
from typing import Any, Optional


def format_date(value: Optional[str | datetime]) -> str:
    """
    Format a date for display.

    Args:
        value: ISO date string or datetime object

    Returns:
        Formatted date string (DD/MM/YYYY) or empty string
    """
    if not value:
        return "-"

    try:
        if isinstance(value, str):
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        else:
            dt = value
        return dt.strftime("%d/%m/%Y")
    except Exception:
        return str(value)


def format_datetime(value: Optional[str | datetime]) -> str:
    """
    Format a datetime for display.

    Args:
        value: ISO datetime string or datetime object

    Returns:
        Formatted datetime string (DD/MM/YYYY HH:MM) or empty string
    """
    if not value:
        return "-"

    try:
        if isinstance(value, str):
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        else:
            dt = value
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(value)


def format_currency(value: Optional[float | str]) -> str:
    """
    Format a value as Brazilian currency.

    Args:
        value: Numeric value

    Returns:
        Formatted currency string (R$ X,XX)
    """
    if value is None:
        return "-"

    try:
        amount = float(value)
        if amount == 0:
            return "-"
        return f"R$ {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(value)


def format_status(status: Optional[str], status_type: str = "loan") -> tuple[str, str]:
    """
    Format a status with label and color.

    Args:
        status: Status string
        status_type: Type of status ('loan', 'reservation', 'copy')

    Returns:
        Tuple of (display_label, color)
    """
    if not status:
        return "-", "gray"

    status = status.upper()

    loan_statuses = {
        "ACTIVE": ("Ativo", "blue"),
        "RETURNED": ("Devolvido", "green"),
        "OVERDUE": ("Atrasado", "red"),
    }

    reservation_statuses = {
        "ACTIVE": ("Na Fila", "blue"),
        "ON_HOLD": ("Reservado", "orange"),
        "FULFILLED": ("Concluída", "green"),
        "EXPIRED": ("Expirada", "red"),
        "CANCELLED": ("Cancelada", "gray"),
    }

    copy_statuses = {
        "AVAILABLE": ("Disponível", "green"),
        "LOANED": ("Emprestado", "blue"),
        "ON_HOLD": ("Reservado", "orange"),
    }

    status_maps = {
        "loan": loan_statuses,
        "reservation": reservation_statuses,
        "copy": copy_statuses,
    }

    status_map = status_maps.get(status_type, {})
    return status_map.get(status, (status, "gray"))


def format_bool(value: Any) -> str:
    """Format a boolean value for display."""
    if value is True:
        return "Sim"
    elif value is False:
        return "Não"
    return "-"


def calculate_days_until(date_str: Optional[str]) -> Optional[int]:
    """
    Calculate days until a given date.

    Args:
        date_str: ISO date string

    Returns:
        Number of days (negative if past)
    """
    if not date_str:
        return None

    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        delta = dt - now
        return delta.days
    except Exception:
        return None


def format_days_remaining(days: Optional[int]) -> str:
    """Format days remaining for display."""
    if days is None:
        return "-"
    if days < 0:
        return f"Atrasado {abs(days)} dia(s)"
    elif days == 0:
        return "Vence hoje"
    elif days == 1:
        return "Vence amanhã"
    else:
        return f"Faltam {days} dias"

"""
Utilitários de segurança: hash de senha e JWT.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def hash_password(password: str) -> str:
    """
    Gera hash bcrypt da senha.

    Args:
        password: Senha em texto plano

    Returns:
        Hash bcrypt da senha
    """
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica se a senha corresponde ao hash.

    Args:
        plain_password: Senha em texto plano
        hashed_password: Hash bcrypt armazenado

    Returns:
        True se a senha está correta
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception as e:
        logger.debug(f"Erro na verificação de senha: {type(e).__name__}")
        return False


def create_access_token(
    subject: str,
    extra_data: dict[str, Any] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Cria token JWT.

    Args:
        subject: Identificador do usuário (geralmente user_id ou email)
        extra_data: Dados adicionais para incluir no payload
        expires_delta: Tempo de expiração customizado

    Returns:
        Token JWT assinado
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.JWT_EXPIRES_MINUTES
        )

    payload = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }

    if extra_data:
        payload.update(extra_data)

    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any] | None:
    """
    Decodifica e valida token JWT.

    Args:
        token: Token JWT

    Returns:
        Payload do token ou None se inválido/expirado
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError:
        return None

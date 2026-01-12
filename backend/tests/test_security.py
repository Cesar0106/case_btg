"""
Testes unitários para funções de segurança.
"""

from datetime import timedelta

import pytest

from app.core.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    """Testes para hash de senha."""

    def test_hash_password_returns_hash(self):
        """Hash deve ser diferente da senha original."""
        password = "MinhaSenh@123"
        hashed = hash_password(password)

        assert hashed != password
        assert len(hashed) > 50  # bcrypt hash tem ~60 caracteres

    def test_hash_password_different_hashes(self):
        """Mesmo password deve gerar hashes diferentes (salt)."""
        password = "MinhaSenh@123"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        assert hash1 != hash2

    def test_verify_password_correct(self):
        """Senha correta deve retornar True."""
        password = "MinhaSenh@123"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Senha incorreta deve retornar False."""
        password = "MinhaSenh@123"
        wrong_password = "SenhaErrada123"
        hashed = hash_password(password)

        assert verify_password(wrong_password, hashed) is False

    def test_verify_password_empty(self):
        """Senha vazia deve retornar False."""
        password = "MinhaSenh@123"
        hashed = hash_password(password)

        assert verify_password("", hashed) is False


class TestJWT:
    """Testes para JWT."""

    def test_create_access_token(self):
        """Token deve ser criado com sucesso."""
        token = create_access_token(subject="user-123")

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 50

    def test_decode_token_valid(self):
        """Token válido deve ser decodificado."""
        user_id = "user-123"
        token = create_access_token(subject=user_id)
        payload = decode_token(token)

        assert payload is not None
        assert payload["sub"] == user_id
        assert "exp" in payload
        assert "iat" in payload

    def test_decode_token_with_extra_data(self):
        """Token com dados extras deve incluí-los no payload."""
        user_id = "user-123"
        extra = {"role": "ADMIN", "email": "admin@test.com"}
        token = create_access_token(subject=user_id, extra_data=extra)
        payload = decode_token(token)

        assert payload is not None
        assert payload["sub"] == user_id
        assert payload["role"] == "ADMIN"
        assert payload["email"] == "admin@test.com"

    def test_decode_token_invalid(self):
        """Token inválido deve retornar None."""
        payload = decode_token("invalid-token")

        assert payload is None

    def test_decode_token_expired(self):
        """Token expirado deve retornar None."""
        token = create_access_token(
            subject="user-123",
            expires_delta=timedelta(seconds=-1),  # já expirado
        )
        payload = decode_token(token)

        assert payload is None

    def test_decode_token_tampered(self):
        """Token adulterado deve retornar None."""
        token = create_access_token(subject="user-123")
        # Modifica o token
        tampered = token[:-5] + "XXXXX"
        payload = decode_token(tampered)

        assert payload is None

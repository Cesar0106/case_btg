"""
Fixtures compartilhadas para testes.

Configuração especial para Windows + asyncpg + pytest-asyncio.
"""

import uuid
from typing import AsyncGenerator

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.security import create_access_token
from app.db.session import Base, get_db
from app.main import app
from app.models.enums import UserRole

settings = get_settings()


# ==========================================
# Event loop configuration
# ==========================================

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


# ==========================================
# Database fixtures
# ==========================================

@pytest.fixture(scope="session")
def test_engine():
    """
    Engine de teste com NullPool para evitar problemas de event loop.

    NullPool não mantém conexões abertas entre requisições,
    evitando o problema de "Event loop is closed" no Windows.
    """
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        poolclass=NullPool,  # Não mantém conexões no pool
    )
    return engine


@pytest.fixture
async def test_db(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Cria sessão de banco para testes.

    Cada teste recebe uma sessão independente.
    """
    async_session = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session


# ==========================================
# HTTP Client fixtures
# ==========================================

@pytest.fixture
async def client(test_engine) -> AsyncGenerator[AsyncClient, None]:
    """
    Cliente HTTP assíncrono para testes.

    Substitui a dependency get_db para usar o engine de teste.
    """
    # Criar session factory para este teste
    async_session = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db():
        async with async_session() as session:
            try:
                yield session
            finally:
                await session.close()

    # Override da dependency
    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    # Limpar override após o teste
    app.dependency_overrides.clear()


# ==========================================
# Auth fixtures
# ==========================================

@pytest.fixture
def admin_token() -> str:
    """
    Token JWT de admin para testes.

    Nota: Em testes de integração reais, criar usuário no banco
    e fazer login. Este fixture é para testes mais simples.
    """
    return create_access_token(
        subject=str(uuid.uuid4()),
        extra_data={"role": UserRole.ADMIN.value},
    )


@pytest.fixture
def user_token() -> str:
    """Token JWT de usuário comum para testes."""
    return create_access_token(
        subject=str(uuid.uuid4()),
        extra_data={"role": UserRole.USER.value},
    )


@pytest.fixture
def auth_headers(admin_token: str) -> dict:
    """Headers de autenticação com token admin."""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def user_headers(user_token: str) -> dict:
    """Headers de autenticação com token usuário."""
    return {"Authorization": f"Bearer {user_token}"}

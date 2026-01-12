"""
Configuração de sessão do banco de dados com SQLAlchemy async.

Este módulo fornece o engine async, session factory e dependency
para injeção de sessão nos endpoints.
"""

from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

# Engine async com pool de conexões
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

# Factory de sessões async
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Classe base para todos os modelos SQLAlchemy."""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency que fornece uma sessão de banco de dados.

    Uso nos endpoints:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...

    A sessão é automaticamente fechada após o request.
    """
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def check_database_connection() -> tuple[bool, str | None]:
    """
    Verifica se a conexão com o banco de dados está funcionando.

    Returns:
        Tupla (sucesso, mensagem_erro)
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True, None
    except Exception as e:
        return False, str(e)

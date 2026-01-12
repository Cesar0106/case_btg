"""
Módulo de banco de dados - conexões e sessões.

Exports:
    - Base: Classe base para modelos SQLAlchemy
    - engine: Engine async do SQLAlchemy
    - get_db: Dependency para injeção de sessão
    - get_redis: Dependency para injeção do cliente Redis
"""

from app.db.session import Base, engine, get_db, async_session_factory
from app.db.redis import get_redis, init_redis, close_redis

__all__ = [
    "Base",
    "engine",
    "get_db",
    "async_session_factory",
    "get_redis",
    "init_redis",
    "close_redis",
]

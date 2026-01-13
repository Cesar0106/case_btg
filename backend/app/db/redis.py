"""
Configuração de conexão com Redis para cache e rate limiting.

Este módulo fornece o cliente Redis e funções utilitárias.
"""

import logging
from typing import Optional

import redis.asyncio as redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Cliente Redis (será inicializado no startup)
redis_client: Optional[redis.Redis] = None


async def init_redis() -> redis.Redis:
    """
    Inicializa a conexão com o Redis.

    Returns:
        Cliente Redis conectado.
    """
    global redis_client
    redis_client = redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )
    return redis_client


async def close_redis() -> None:
    """Fecha a conexão com o Redis."""
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None


async def get_redis() -> redis.Redis:
    """
    Dependency que fornece o cliente Redis.

    Uso nos endpoints:
        @app.get("/cached")
        async def get_cached(redis: Redis = Depends(get_redis)):
            ...
    """
    if redis_client is None:
        raise RuntimeError("Redis não inicializado. Chame init_redis() primeiro.")
    return redis_client


async def check_redis_connection() -> bool:
    """
    Verifica se a conexão com o Redis está funcionando.

    Returns:
        True se conectou com sucesso, False caso contrário.
    """
    try:
        if redis_client:
            await redis_client.ping()
            return True
        return False
    except Exception as e:
        logger.warning(f"Erro ao verificar conexão Redis: {e}")
        return False

"""
Cache service usando Redis.

Fornece cache para endpoints com alta frequência de acesso.
Configurável via variáveis de ambiente:
    - CACHE_ENABLED: bool (default: True) - Habilita/desabilita cache
    - CACHE_AVAILABILITY_TTL_SECONDS: int (default: 15) - TTL do cache de availability

Uso:
    cache = CacheService()

    # Buscar do cache
    data = await cache.get_availability(book_id)
    if data:
        return data

    # Calcular e salvar no cache
    result = await compute_availability()
    await cache.set_availability(book_id, result)
    return result

Invalidação:
    # Invalidar ao emprestar/devolver
    await cache.invalidate_availability(book_id)
"""

import json
import logging
from typing import Any, Optional
from uuid import UUID

from app.core.config import get_settings
from app.db.redis import redis_client

logger = logging.getLogger(__name__)
settings = get_settings()


class CacheService:
    """
    Service para operações de cache usando Redis.

    Implementa cache para:
        - Availability de livros (GET /books/{id}/availability)

    Com invalidação automática em operações de:
        - create_loan
        - return_loan
        - process_holds
    """

    # Prefixos de chave
    PREFIX_AVAILABILITY = "cache:availability"

    def __init__(self, ttl: Optional[int] = None):
        """
        Inicializa o cache service.

        Args:
            ttl: TTL padrão em segundos (default: config)
        """
        self.ttl = ttl or settings.CACHE_AVAILABILITY_TTL_SECONDS

    # ==========================================
    # Availability Cache
    # ==========================================

    async def get_availability(self, book_title_id: UUID) -> Optional[dict]:
        """
        Busca availability do cache.

        Args:
            book_title_id: ID do título do livro

        Returns:
            Dados de availability ou None se não em cache
        """
        if not settings.CACHE_ENABLED or redis_client is None:
            return None

        try:
            key = f"{self.PREFIX_AVAILABILITY}:{book_title_id}"
            data = await redis_client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.warning(f"Erro ao buscar cache availability: {e}")
            return None

    async def set_availability(
        self,
        book_title_id: UUID,
        data: dict,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Salva availability no cache.

        Args:
            book_title_id: ID do título do livro
            data: Dados de availability
            ttl: TTL em segundos (default: self.ttl)

        Returns:
            True se salvou com sucesso, False caso contrário
        """
        if not settings.CACHE_ENABLED or redis_client is None:
            return False

        try:
            key = f"{self.PREFIX_AVAILABILITY}:{book_title_id}"
            await redis_client.setex(
                key,
                ttl or self.ttl,
                json.dumps(data, default=str),
            )
            return True
        except Exception as e:
            logger.warning(f"Erro ao salvar cache availability: {e}")
            return False

    async def invalidate_availability(self, book_title_id: UUID) -> bool:
        """
        Invalida cache de availability para um título.

        Deve ser chamado após:
            - create_loan (cópia emprestada)
            - return_loan (cópia devolvida)
            - process_holds (cópia reservada)
            - expire_holds (cópia liberada)

        Args:
            book_title_id: ID do título do livro

        Returns:
            True se invalidou com sucesso, False caso contrário
        """
        if not settings.CACHE_ENABLED or redis_client is None:
            return False

        try:
            key = f"{self.PREFIX_AVAILABILITY}:{book_title_id}"
            await redis_client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Erro ao invalidar cache availability: {e}")
            return False

    async def invalidate_all_availability(self) -> int:
        """
        Invalida todo o cache de availability.

        Útil para operações em massa ou manutenção.

        Returns:
            Número de chaves deletadas
        """
        if not settings.CACHE_ENABLED or redis_client is None:
            return 0

        try:
            pattern = f"{self.PREFIX_AVAILABILITY}:*"
            keys = []
            async for key in redis_client.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                return await redis_client.delete(*keys)
            return 0
        except Exception as e:
            logger.warning(f"Erro ao invalidar todo cache availability: {e}")
            return 0


# Instância global para uso nos services
cache_service = CacheService()

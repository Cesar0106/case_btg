"""
Testes unitários para Rate Limiting e Cache.

Usa mocks para Redis para testar a lógica sem dependência externa.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi import HTTPException, Request


# ==========================================
# Tests para RateLimiter
# ==========================================

class TestRateLimiter:
    """Testes para o RateLimiter."""

    @pytest.fixture
    def mock_request(self):
        """Cria mock de Request."""
        request = MagicMock(spec=Request)
        request.client.host = "127.0.0.1"
        request.headers = {}
        return request

    @pytest.fixture
    def mock_credentials(self):
        """Cria mock de credenciais com JWT válido."""
        credentials = MagicMock()
        credentials.credentials = "fake_token"
        return credentials

    @pytest.mark.asyncio
    async def test_rate_limit_disabled_allows_all(self, mock_request):
        """Quando rate limit está desabilitado, permite todas as requisições."""
        with patch("app.core.rate_limit.settings") as mock_settings:
            mock_settings.RATE_LIMIT_ENABLED = False

            from app.core.rate_limit import RateLimiter
            limiter = RateLimiter()

            # Não deve lançar exceção
            await limiter(mock_request, None)

    @pytest.mark.asyncio
    async def test_rate_limit_redis_unavailable_allows_all(self, mock_request):
        """Quando Redis não está disponível, permite (fail-open)."""
        with patch("app.core.rate_limit.settings") as mock_settings, \
             patch("app.core.rate_limit.redis_client", None):
            mock_settings.RATE_LIMIT_ENABLED = True

            from app.core.rate_limit import RateLimiter
            limiter = RateLimiter()

            # Não deve lançar exceção
            await limiter(mock_request, None)

    @pytest.mark.asyncio
    async def test_rate_limit_first_request_success(self, mock_request):
        """Primeira requisição deve passar e definir TTL."""
        mock_redis = AsyncMock()
        mock_redis.incr.return_value = 1  # Primeira requisição

        with patch("app.core.rate_limit.settings") as mock_settings, \
             patch("app.core.rate_limit.redis_client", mock_redis):
            mock_settings.RATE_LIMIT_ENABLED = True
            mock_settings.RATE_LIMIT_REQUESTS = 60
            mock_settings.RATE_LIMIT_WINDOW_SECONDS = 60

            from app.core.rate_limit import RateLimiter
            limiter = RateLimiter()

            await limiter(mock_request, None)

            # Deve ter chamado incr e expire
            mock_redis.incr.assert_called_once()
            mock_redis.expire.assert_called_once()

    @pytest.mark.asyncio
    async def test_rate_limit_within_limit_success(self, mock_request):
        """Requisições dentro do limite devem passar."""
        mock_redis = AsyncMock()
        mock_redis.incr.return_value = 30  # Dentro do limite de 60

        with patch("app.core.rate_limit.settings") as mock_settings, \
             patch("app.core.rate_limit.redis_client", mock_redis):
            mock_settings.RATE_LIMIT_ENABLED = True
            mock_settings.RATE_LIMIT_REQUESTS = 60
            mock_settings.RATE_LIMIT_WINDOW_SECONDS = 60

            from app.core.rate_limit import RateLimiter
            limiter = RateLimiter()

            await limiter(mock_request, None)

            # Não deve lançar exceção
            mock_redis.incr.assert_called_once()

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded_raises_429(self, mock_request):
        """Quando limite é excedido, deve lançar 429."""
        mock_redis = AsyncMock()
        mock_redis.incr.return_value = 61  # Excede limite de 60
        mock_redis.ttl.return_value = 45

        with patch("app.core.rate_limit.settings") as mock_settings, \
             patch("app.core.rate_limit.redis_client", mock_redis):
            mock_settings.RATE_LIMIT_ENABLED = True
            mock_settings.RATE_LIMIT_REQUESTS = 60
            mock_settings.RATE_LIMIT_WINDOW_SECONDS = 60

            from app.core.rate_limit import RateLimiter
            limiter = RateLimiter()

            with pytest.raises(HTTPException) as exc_info:
                await limiter(mock_request, None)

            assert exc_info.value.status_code == 429
            assert "Rate limit excedido" in exc_info.value.detail
            assert exc_info.value.headers["Retry-After"] == "45"

    @pytest.mark.asyncio
    async def test_rate_limit_identifies_by_jwt(self, mock_request, mock_credentials):
        """Deve identificar usuário por JWT quando autenticado."""
        mock_redis = AsyncMock()
        mock_redis.incr.return_value = 1

        user_id = str(uuid4())

        with patch("app.core.rate_limit.settings") as mock_settings, \
             patch("app.core.rate_limit.redis_client", mock_redis), \
             patch("app.core.rate_limit.decode_token") as mock_decode:
            mock_settings.RATE_LIMIT_ENABLED = True
            mock_settings.RATE_LIMIT_REQUESTS = 60
            mock_settings.RATE_LIMIT_WINDOW_SECONDS = 60
            mock_decode.return_value = {"sub": user_id}

            from app.core.rate_limit import RateLimiter
            limiter = RateLimiter()

            await limiter(mock_request, mock_credentials)

            # Verifica que usou o user_id como identificador
            call_args = mock_redis.incr.call_args[0][0]
            assert f"user:{user_id}" in call_args

    @pytest.mark.asyncio
    async def test_rate_limit_identifies_by_ip_when_anonymous(self, mock_request):
        """Deve identificar por IP quando não autenticado."""
        mock_redis = AsyncMock()
        mock_redis.incr.return_value = 1

        with patch("app.core.rate_limit.settings") as mock_settings, \
             patch("app.core.rate_limit.redis_client", mock_redis):
            mock_settings.RATE_LIMIT_ENABLED = True
            mock_settings.RATE_LIMIT_REQUESTS = 60
            mock_settings.RATE_LIMIT_WINDOW_SECONDS = 60

            from app.core.rate_limit import RateLimiter
            limiter = RateLimiter()

            await limiter(mock_request, None)

            # Verifica que usou IP como identificador
            call_args = mock_redis.incr.call_args[0][0]
            assert "ip:127.0.0.1" in call_args

    @pytest.mark.asyncio
    async def test_rate_limit_uses_x_forwarded_for(self, mock_request):
        """Deve usar X-Forwarded-For quando disponível."""
        mock_redis = AsyncMock()
        mock_redis.incr.return_value = 1
        mock_request.headers = {"X-Forwarded-For": "10.0.0.1, 192.168.1.1"}

        with patch("app.core.rate_limit.settings") as mock_settings, \
             patch("app.core.rate_limit.redis_client", mock_redis):
            mock_settings.RATE_LIMIT_ENABLED = True
            mock_settings.RATE_LIMIT_REQUESTS = 60
            mock_settings.RATE_LIMIT_WINDOW_SECONDS = 60

            from app.core.rate_limit import RateLimiter
            limiter = RateLimiter()

            await limiter(mock_request, None)

            # Verifica que usou primeiro IP do X-Forwarded-For
            call_args = mock_redis.incr.call_args[0][0]
            assert "ip:10.0.0.1" in call_args

    @pytest.mark.asyncio
    async def test_rate_limit_custom_parameters(self, mock_request):
        """Deve respeitar parâmetros customizados."""
        mock_redis = AsyncMock()
        mock_redis.incr.return_value = 11  # Excede limite customizado de 10
        mock_redis.ttl.return_value = 30

        with patch("app.core.rate_limit.settings") as mock_settings, \
             patch("app.core.rate_limit.redis_client", mock_redis):
            mock_settings.RATE_LIMIT_ENABLED = True
            mock_settings.RATE_LIMIT_REQUESTS = 60  # Default
            mock_settings.RATE_LIMIT_WINDOW_SECONDS = 60

            from app.core.rate_limit import RateLimiter
            limiter = RateLimiter(requests=10, window=30)

            with pytest.raises(HTTPException) as exc_info:
                await limiter(mock_request, None)

            assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_rate_limit_redis_error_allows_request(self, mock_request):
        """Erro no Redis deve permitir requisição (fail-open)."""
        mock_redis = AsyncMock()
        mock_redis.incr.side_effect = Exception("Redis connection error")

        with patch("app.core.rate_limit.settings") as mock_settings, \
             patch("app.core.rate_limit.redis_client", mock_redis):
            mock_settings.RATE_LIMIT_ENABLED = True
            mock_settings.RATE_LIMIT_REQUESTS = 60
            mock_settings.RATE_LIMIT_WINDOW_SECONDS = 60

            from app.core.rate_limit import RateLimiter
            limiter = RateLimiter()

            # Não deve lançar exceção
            await limiter(mock_request, None)


# ==========================================
# Tests para CacheService
# ==========================================

class TestCacheService:
    """Testes para o CacheService."""

    @pytest.fixture
    def book_id(self):
        """ID de livro para testes."""
        return uuid4()

    @pytest.fixture
    def availability_data(self):
        """Dados de disponibilidade para testes."""
        return {
            "available": True,
            "reason": None,
            "expected_due_date": None,
            "available_copies": 2,
            "total_copies": 5,
        }

    @pytest.mark.asyncio
    async def test_cache_disabled_get_returns_none(self, book_id):
        """Quando cache está desabilitado, get retorna None."""
        with patch("app.core.cache.settings") as mock_settings:
            mock_settings.CACHE_ENABLED = False
            mock_settings.CACHE_AVAILABILITY_TTL_SECONDS = 15

            from app.core.cache import CacheService
            cache = CacheService()

            result = await cache.get_availability(book_id)
            assert result is None

    @pytest.mark.asyncio
    async def test_cache_disabled_set_returns_false(self, book_id, availability_data):
        """Quando cache está desabilitado, set retorna False."""
        with patch("app.core.cache.settings") as mock_settings:
            mock_settings.CACHE_ENABLED = False
            mock_settings.CACHE_AVAILABILITY_TTL_SECONDS = 15

            from app.core.cache import CacheService
            cache = CacheService()

            result = await cache.set_availability(book_id, availability_data)
            assert result is False

    @pytest.mark.asyncio
    async def test_cache_redis_unavailable_get_returns_none(self, book_id):
        """Quando Redis não está disponível, get retorna None."""
        with patch("app.core.cache.settings") as mock_settings, \
             patch("app.core.cache.redis_client", None):
            mock_settings.CACHE_ENABLED = True
            mock_settings.CACHE_AVAILABILITY_TTL_SECONDS = 15

            from app.core.cache import CacheService
            cache = CacheService()

            result = await cache.get_availability(book_id)
            assert result is None

    @pytest.mark.asyncio
    async def test_cache_get_hit(self, book_id, availability_data):
        """Deve retornar dados do cache quando existem."""
        import json
        mock_redis = AsyncMock()
        mock_redis.get.return_value = json.dumps(availability_data)

        with patch("app.core.cache.settings") as mock_settings, \
             patch("app.core.cache.redis_client", mock_redis):
            mock_settings.CACHE_ENABLED = True
            mock_settings.CACHE_AVAILABILITY_TTL_SECONDS = 15

            from app.core.cache import CacheService
            cache = CacheService()

            result = await cache.get_availability(book_id)

            assert result == availability_data
            mock_redis.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_get_miss(self, book_id):
        """Deve retornar None quando não há dados no cache."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        with patch("app.core.cache.settings") as mock_settings, \
             patch("app.core.cache.redis_client", mock_redis):
            mock_settings.CACHE_ENABLED = True
            mock_settings.CACHE_AVAILABILITY_TTL_SECONDS = 15

            from app.core.cache import CacheService
            cache = CacheService()

            result = await cache.get_availability(book_id)

            assert result is None

    @pytest.mark.asyncio
    async def test_cache_set_success(self, book_id, availability_data):
        """Deve salvar dados no cache com TTL."""
        mock_redis = AsyncMock()

        with patch("app.core.cache.settings") as mock_settings, \
             patch("app.core.cache.redis_client", mock_redis):
            mock_settings.CACHE_ENABLED = True
            mock_settings.CACHE_AVAILABILITY_TTL_SECONDS = 15

            from app.core.cache import CacheService
            cache = CacheService()

            result = await cache.set_availability(book_id, availability_data)

            assert result is True
            mock_redis.setex.assert_called_once()
            # Verifica TTL
            call_args = mock_redis.setex.call_args
            assert call_args[0][1] == 15  # TTL

    @pytest.mark.asyncio
    async def test_cache_set_custom_ttl(self, book_id, availability_data):
        """Deve usar TTL customizado quando fornecido."""
        mock_redis = AsyncMock()

        with patch("app.core.cache.settings") as mock_settings, \
             patch("app.core.cache.redis_client", mock_redis):
            mock_settings.CACHE_ENABLED = True
            mock_settings.CACHE_AVAILABILITY_TTL_SECONDS = 15

            from app.core.cache import CacheService
            cache = CacheService()

            result = await cache.set_availability(book_id, availability_data, ttl=30)

            assert result is True
            call_args = mock_redis.setex.call_args
            assert call_args[0][1] == 30  # TTL customizado

    @pytest.mark.asyncio
    async def test_cache_invalidate_success(self, book_id):
        """Deve invalidar cache de um título."""
        mock_redis = AsyncMock()

        with patch("app.core.cache.settings") as mock_settings, \
             patch("app.core.cache.redis_client", mock_redis):
            mock_settings.CACHE_ENABLED = True
            mock_settings.CACHE_AVAILABILITY_TTL_SECONDS = 15

            from app.core.cache import CacheService
            cache = CacheService()

            result = await cache.invalidate_availability(book_id)

            assert result is True
            mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_invalidate_all_success(self):
        """Deve invalidar todo o cache de availability."""
        mock_redis = AsyncMock()
        # Simula scan_iter retornando chaves
        keys = ["cache:availability:id1", "cache:availability:id2"]

        async def mock_scan_iter(match):
            for key in keys:
                yield key

        mock_redis.scan_iter = mock_scan_iter
        mock_redis.delete.return_value = 2

        with patch("app.core.cache.settings") as mock_settings, \
             patch("app.core.cache.redis_client", mock_redis):
            mock_settings.CACHE_ENABLED = True
            mock_settings.CACHE_AVAILABILITY_TTL_SECONDS = 15

            from app.core.cache import CacheService
            cache = CacheService()

            result = await cache.invalidate_all_availability()

            assert result == 2
            mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_get_error_returns_none(self, book_id):
        """Erro no Redis ao buscar cache deve retornar None."""
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = Exception("Redis error")

        with patch("app.core.cache.settings") as mock_settings, \
             patch("app.core.cache.redis_client", mock_redis):
            mock_settings.CACHE_ENABLED = True
            mock_settings.CACHE_AVAILABILITY_TTL_SECONDS = 15

            from app.core.cache import CacheService
            cache = CacheService()

            result = await cache.get_availability(book_id)
            assert result is None

    @pytest.mark.asyncio
    async def test_cache_set_error_returns_false(self, book_id, availability_data):
        """Erro no Redis ao salvar cache deve retornar False."""
        mock_redis = AsyncMock()
        mock_redis.setex.side_effect = Exception("Redis error")

        with patch("app.core.cache.settings") as mock_settings, \
             patch("app.core.cache.redis_client", mock_redis):
            mock_settings.CACHE_ENABLED = True
            mock_settings.CACHE_AVAILABILITY_TTL_SECONDS = 15

            from app.core.cache import CacheService
            cache = CacheService()

            result = await cache.set_availability(book_id, availability_data)
            assert result is False

    @pytest.mark.asyncio
    async def test_cache_key_format(self, book_id):
        """Verifica formato correto da chave de cache."""
        import json
        mock_redis = AsyncMock()
        mock_redis.get.return_value = json.dumps({"available": True})

        with patch("app.core.cache.settings") as mock_settings, \
             patch("app.core.cache.redis_client", mock_redis):
            mock_settings.CACHE_ENABLED = True
            mock_settings.CACHE_AVAILABILITY_TTL_SECONDS = 15

            from app.core.cache import CacheService
            cache = CacheService()

            await cache.get_availability(book_id)

            # Verifica formato da chave
            call_args = mock_redis.get.call_args[0][0]
            assert call_args == f"cache:availability:{book_id}"

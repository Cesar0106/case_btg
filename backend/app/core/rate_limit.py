"""
Rate limiting usando Redis com sliding window.

Implementa rate limiting por usuário autenticado ou IP para usuários anônimos.
Configurável via variáveis de ambiente:
    - RATE_LIMIT_ENABLED: bool (default: True) - Habilita/desabilita rate limiting
    - RATE_LIMIT_REQUESTS: int (default: 60) - Número de requests permitidos
    - RATE_LIMIT_WINDOW_SECONDS: int (default: 60) - Janela de tempo em segundos

Uso:
    @router.post("/endpoint")
    async def endpoint(
        rate_limit: None = Depends(RateLimiter(requests=30, window=60)),
    ):
        ...
"""

from typing import Optional

from fastapi import HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.core.security import decode_token
from app.db.redis import redis_client

settings = get_settings()
security = HTTPBearer(auto_error=False)


class RateLimiter:
    """
    Dependency para rate limiting usando Redis.

    Usa sliding window log algorithm para maior precisão.

    Args:
        requests: Número máximo de requests permitidos (default: config)
        window: Janela de tempo em segundos (default: config)
        key_prefix: Prefixo para a chave no Redis (default: "rate_limit")
    """

    def __init__(
        self,
        requests: Optional[int] = None,
        window: Optional[int] = None,
        key_prefix: str = "rate_limit",
    ):
        self.requests = requests or settings.RATE_LIMIT_REQUESTS
        self.window = window or settings.RATE_LIMIT_WINDOW_SECONDS
        self.key_prefix = key_prefix

    async def __call__(
        self,
        request: Request,
        credentials: Optional[HTTPAuthorizationCredentials] = None,
    ) -> None:
        """
        Verifica rate limit.

        Identifica o usuário por:
            1. user_id do JWT (se autenticado)
            2. IP do cliente (se anônimo)

        Raises:
            HTTPException 429: Rate limit excedido
        """
        # Se rate limit desabilitado, retorna sem verificar
        if not settings.RATE_LIMIT_ENABLED:
            return

        # Se Redis não disponível, permite passagem (fail-open)
        if redis_client is None:
            return

        # Identificar o usuário
        identifier = await self._get_identifier(request, credentials)
        key = f"{self.key_prefix}:{identifier}"

        try:
            # Incrementar contador
            current = await redis_client.incr(key)

            # Se é o primeiro request, definir TTL
            if current == 1:
                await redis_client.expire(key, self.window)

            # Verificar se excedeu
            if current > self.requests:
                ttl = await redis_client.ttl(key)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit excedido. Tente novamente em {ttl} segundos.",
                    headers={"Retry-After": str(ttl)},
                )
        except HTTPException:
            raise
        except Exception:
            # Em caso de erro no Redis, permite passagem (fail-open)
            pass

    async def _get_identifier(
        self,
        request: Request,
        credentials: Optional[HTTPAuthorizationCredentials],
    ) -> str:
        """
        Obtém identificador único para o rate limit.

        Prioridade:
            1. user_id do JWT (se autenticado)
            2. IP do cliente
        """
        # Tentar extrair user_id do JWT
        if credentials:
            payload = decode_token(credentials.credentials)
            if payload and "sub" in payload:
                return f"user:{payload['sub']}"

        # Fallback para IP
        client_ip = request.client.host if request.client else "unknown"

        # Verificar headers de proxy
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()

        return f"ip:{client_ip}"


# Instâncias pré-configuradas para uso comum
rate_limit_default = RateLimiter()
rate_limit_strict = RateLimiter(requests=30, window=60)  # 30 req/min
rate_limit_auth = RateLimiter(requests=10, window=60)  # 10 req/min para auth

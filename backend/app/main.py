"""
Ponto de entrada da aplicação FastAPI.

Este módulo configura a aplicação FastAPI, inclui rotas e define
handlers de ciclo de vida (startup/shutdown).
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import setup_logging, get_logger
from app.db.session import check_database_connection, engine
from app.db.redis import init_redis, close_redis, check_redis_connection
from app.schemas.health import HealthResponse

settings = get_settings()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerencia o ciclo de vida da aplicação.

    Startup:
        - Configura logging
        - Conecta ao Redis
        - Verifica conexão com PostgreSQL

    Shutdown:
        - Fecha conexão com Redis
        - Fecha pool de conexões do banco
    """
    # Startup
    setup_logging()
    logger.info(f"Iniciando {settings.APP_NAME} em ambiente {settings.ENVIRONMENT}")

    # Inicializa Redis
    try:
        await init_redis()
        if await check_redis_connection():
            logger.info("Conexão com Redis estabelecida")
        else:
            logger.warning("Redis não disponível - cache desabilitado")
    except Exception as e:
        logger.warning(f"Falha ao conectar ao Redis: {e}")

    # Verifica PostgreSQL
    try:
        success, error = await check_database_connection()
        if success:
            logger.info("Conexão com PostgreSQL estabelecida")
        else:
            logger.warning(f"PostgreSQL não disponível: {error}")
    except Exception as e:
        logger.warning(f"Falha ao conectar ao PostgreSQL: {e}")

    yield

    # Shutdown
    logger.info(f"Encerrando {settings.APP_NAME}")
    await close_redis()
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    description="API REST para sistema de gerenciamento de biblioteca",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Inclui rotas da API v1
app.include_router(api_router)


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Verifica status da aplicação",
    description="Retorna o status atual da aplicação e informações básicas do ambiente.",
)
async def health_check() -> HealthResponse:
    """
    Endpoint de healthcheck para monitoramento.

    Retorna status da aplicação, nome e ambiente.
    Útil para load balancers e sistemas de monitoramento.
    """
    return HealthResponse(
        status="healthy",
        app_name=settings.APP_NAME,
        environment=settings.ENVIRONMENT,
    )

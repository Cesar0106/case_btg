"""
Ponto de entrada da aplicação FastAPI.

Este módulo configura a aplicação FastAPI, inclui rotas e define
handlers de ciclo de vida (startup/shutdown).
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.logging import setup_logging, get_logger
from app.schemas.health import HealthResponse

settings = get_settings()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerencia o ciclo de vida da aplicação.

    Startup:
        - Configura logging
        - Futuramente: conecta ao banco e Redis

    Shutdown:
        - Futuramente: fecha conexões
    """
    # Startup
    setup_logging()
    logger.info(f"Iniciando {settings.APP_NAME} em ambiente {settings.ENVIRONMENT}")
    yield
    # Shutdown
    logger.info(f"Encerrando {settings.APP_NAME}")


app = FastAPI(
    title=settings.APP_NAME,
    description="API REST para sistema de gerenciamento de biblioteca",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


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

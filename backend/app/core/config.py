"""
Configuração centralizada da aplicação via Pydantic Settings.

Carrega variáveis de ambiente do arquivo .env e valida tipos automaticamente.
Todas as configurações sensíveis devem ser definidas via variáveis de ambiente.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configurações da aplicação carregadas de variáveis de ambiente.

    Attributes:
        APP_NAME: Nome da aplicação exibido na documentação
        DEBUG: Habilita modo debug (não usar em produção)
        ENVIRONMENT: Ambiente atual (development, staging, production)
        HOST: Host para bind do servidor
        PORT: Porta para bind do servidor
        DATABASE_URL: URL de conexão PostgreSQL (async)
        REDIS_URL: URL de conexão Redis
        JWT_SECRET: Chave secreta para assinatura JWT
        JWT_ALGORITHM: Algoritmo de assinatura JWT
        JWT_EXPIRES_MINUTES: Tempo de expiração do token JWT em minutos
        ADMIN_EMAIL: Email do admin seed
        ADMIN_PASSWORD: Senha do admin seed
        LOG_LEVEL: Nível de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "Library API"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/library_db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT Authentication
    JWT_SECRET: str = "jvW2p9cQKx7nL4rT0uY1mZ8aS6eH3dN5fB2kP7xC1qV9tR4nL0uY6mZ8aS3eH1d"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRES_MINUTES: int = 30

    # Admin Seed
    ADMIN_EMAIL: str = "cesar.ezra@ades.as"
    ADMIN_PASSWORD: str = "Admin123!"

    # Logging
    LOG_LEVEL: str = "INFO"

    @property
    def is_production(self) -> bool:
        """Verifica se está em ambiente de produção."""
        return self.ENVIRONMENT == "production"

    @property
    def database_url_async(self) -> str:
        """Retorna a URL do banco para uso com driver async."""
        return self.DATABASE_URL


@lru_cache
def get_settings() -> Settings:
    """
    Retorna instância cacheada das configurações.

    Usa lru_cache para evitar recarregar .env em cada chamada.
    """
    return Settings()

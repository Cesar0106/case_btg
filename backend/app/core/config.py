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
        DATABASE_URL: URL de conexão PostgreSQL
        REDIS_URL: URL de conexão Redis
        SECRET_KEY: Chave secreta para JWT e criptografia
        ACCESS_TOKEN_EXPIRE_MINUTES: Tempo de expiração do token JWT
        ALGORITHM: Algoritmo de assinatura JWT
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
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/library_db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Security
    SECRET_KEY: str = "your-super-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ALGORITHM: str = "HS256"

    # Admin Seed
    ADMIN_EMAIL: str = "admin@local.dev"
    ADMIN_PASSWORD: str = "Admin123!"

    # Logging
    LOG_LEVEL: str = "INFO"

    @property
    def is_production(self) -> bool:
        """Verifica se está em ambiente de produção."""
        return self.ENVIRONMENT == "production"


@lru_cache
def get_settings() -> Settings:
    """
    Retorna instância cacheada das configurações.

    Usa lru_cache para evitar recarregar .env em cada chamada.
    """
    return Settings()

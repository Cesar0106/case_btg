"""
Schemas Pydantic para o endpoint de healthcheck.
"""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """
    Resposta do endpoint de healthcheck.

    Attributes:
        status: Status da aplicação ("healthy" ou "unhealthy")
        app_name: Nome da aplicação
        environment: Ambiente atual (development, staging, production)
    """

    status: str
    app_name: str
    environment: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "healthy",
                    "app_name": "Library API",
                    "environment": "development"
                }
            ]
        }
    }

"""
Configuração de logging estruturado para a aplicação.

Fornece logging configurável via variável de ambiente LOG_LEVEL.
O formato inclui timestamp, nível, nome do logger e mensagem.
"""

import logging
import sys
from typing import Optional

from app.core.config import get_settings


def setup_logging(level: Optional[str] = None) -> None:
    """
    Configura o sistema de logging da aplicação.

    Args:
        level: Nível de logging. Se não fornecido, usa LOG_LEVEL do .env

    O formato do log inclui:
    - Timestamp ISO
    - Nível (colorido no terminal)
    - Nome do logger
    - Mensagem
    """
    settings = get_settings()
    log_level = level or settings.LOG_LEVEL

    # Formato estruturado
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Configura handler para stdout
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))

    # Configura root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level.upper())

    # Remove handlers existentes para evitar duplicação
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Reduz verbosidade de loggers de terceiros
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    # Log inicial
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configurado com nível: {log_level.upper()}")


def get_logger(name: str) -> logging.Logger:
    """
    Retorna um logger configurado para o módulo especificado.

    Args:
        name: Nome do módulo (geralmente __name__)

    Returns:
        Logger configurado
    """
    return logging.getLogger(name)

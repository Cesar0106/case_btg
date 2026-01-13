"""
Script de seed para criar dados iniciais no banco.

Uso:
    python -m app.db.seed

Cria o usuário admin se não existir.
"""

import asyncio
import logging

from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import async_session_factory
from app.models.user import User
from app.models.enums import UserRole

logger = logging.getLogger(__name__)
settings = get_settings()


async def create_admin() -> None:
    """
    Cria usuário admin se não existir.

    Lê email e senha do .env (ADMIN_EMAIL, ADMIN_PASSWORD).
    """
    async with async_session_factory() as db:
        result = await db.execute(
            select(User).where(User.email == settings.ADMIN_EMAIL)
        )
        existing = result.scalar_one_or_none()

        if existing:
            logger.info(f"Admin já existe: {settings.ADMIN_EMAIL}")
            return

        admin = User(
            name="Administrador",
            email=settings.ADMIN_EMAIL,
            password_hash=hash_password(settings.ADMIN_PASSWORD),
            role=UserRole.ADMIN,
        )
        db.add(admin)
        await db.commit()
        await db.refresh(admin)

        logger.info(f"Admin criado: {settings.ADMIN_EMAIL} (ID: {admin.id})")


async def main() -> None:
    """Executa todos os seeds."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger.info("Executando seeds...")
    await create_admin()
    logger.info("Seeds concluídos!")


if __name__ == "__main__":
    asyncio.run(main())

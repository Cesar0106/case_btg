"""
Script de seed para criar dados iniciais no banco.

Uso:
    python -m app.db.seed

Cria o usuário admin se não existir.
"""

import asyncio
import sys

from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import async_session_factory
from app.models.user import User
from app.models.enums import UserRole

settings = get_settings()


async def create_admin() -> None:
    """
    Cria usuário admin se não existir.

    Lê email e senha do .env (ADMIN_EMAIL, ADMIN_PASSWORD).
    """
    async with async_session_factory() as db:
        # Verifica se admin já existe
        result = await db.execute(
            select(User).where(User.email == settings.ADMIN_EMAIL)
        )
        existing = result.scalar_one_or_none()

        if existing:
            print(f"Admin já existe: {settings.ADMIN_EMAIL}")
            return

        # Cria admin
        admin = User(
            name="Administrador",
            email=settings.ADMIN_EMAIL,
            password_hash=hash_password(settings.ADMIN_PASSWORD),
            role=UserRole.ADMIN,
        )
        db.add(admin)
        await db.commit()
        await db.refresh(admin)

        print(f"Admin criado com sucesso!")
        print(f"  Email: {settings.ADMIN_EMAIL}")
        print(f"  Role: ADMIN")
        print(f"  ID: {admin.id}")


async def main() -> None:
    """Executa todos os seeds."""
    print("=" * 50)
    print("Executando seeds...")
    print("=" * 50)

    await create_admin()

    print("=" * 50)
    print("Seeds concluídos!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())

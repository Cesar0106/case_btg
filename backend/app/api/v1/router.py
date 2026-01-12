"""
Router principal da API v1.

Inclui todos os routers de endpoints.
"""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.authors import router as authors_router
from app.api.v1.books import router as books_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth_router)
api_router.include_router(authors_router)
api_router.include_router(books_router)

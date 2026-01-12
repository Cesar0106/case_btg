"""
Módulo de repositórios - acesso a dados.
"""

from app.repositories.base import BaseRepository
from app.repositories.user import UserRepository
from app.repositories.author import AuthorRepository
from app.repositories.book import BookTitleRepository, BookCopyRepository
from app.repositories.loan import LoanRepository

__all__ = [
    "BaseRepository",
    "UserRepository",
    "AuthorRepository",
    "BookTitleRepository",
    "BookCopyRepository",
    "LoanRepository",
]

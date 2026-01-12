"""
Schemas Pydantic da aplicação.
"""

from app.schemas.base import (
    BaseSchema,
    ErrorDetail,
    ErrorResponse,
    MessageResponse,
    PaginatedResponse,
    TimestampSchema,
)
from app.schemas.health import HealthResponse
from app.schemas.user import (
    TokenResponse,
    UserCreate,
    UserLogin,
    UserRead,
    UserUpdate,
    UserWithToken,
)
from app.schemas.author import (
    AuthorCreate,
    AuthorRead,
    AuthorUpdate,
    AuthorWithBooks,
)
from app.schemas.book import (
    BookAvailability,
    BookCopyCreate,
    BookCopyRead,
    BookCopyUpdate,
    BookCopyWithTitle,
    BookTitleCreate,
    BookTitleDetail,
    BookTitleRead,
    BookTitleUpdate,
    BookTitleWithAuthor,
)

__all__ = [
    # Base
    "BaseSchema",
    "ErrorDetail",
    "ErrorResponse",
    "MessageResponse",
    "PaginatedResponse",
    "TimestampSchema",
    # Health
    "HealthResponse",
    # User
    "TokenResponse",
    "UserCreate",
    "UserLogin",
    "UserRead",
    "UserUpdate",
    "UserWithToken",
    # Author
    "AuthorCreate",
    "AuthorRead",
    "AuthorUpdate",
    "AuthorWithBooks",
    # Book
    "BookAvailability",
    "BookCopyCreate",
    "BookCopyRead",
    "BookCopyUpdate",
    "BookCopyWithTitle",
    "BookTitleCreate",
    "BookTitleDetail",
    "BookTitleRead",
    "BookTitleUpdate",
    "BookTitleWithAuthor",
]

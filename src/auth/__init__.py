"""
Authentication module — public API surface.

Re-exports the FastAPI router and dependency-injection helpers so that
``auth_server.py`` (or any other host application) only needs::

    from src.auth import auth_router, get_current_user

Keeping imports centralised here shields consumers from internal
restructuring.
"""

from src.auth.api import router as auth_router
from src.auth.vault_api import router as vault_router
from src.auth.dependencies import get_auth_service, get_current_user, require_roles

__all__ = [
    "auth_router",
    "vault_router",
    "get_auth_service",
    "get_current_user",
    "require_roles",
]

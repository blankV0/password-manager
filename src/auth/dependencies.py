"""
FastAPI dependency-injection wiring.

Instantiates the singleton :class:`~src.auth.service.AuthService` and
its collaborators (database, rate limiter) **once** at import time,
then exposes lightweight callables that FastAPI resolves per-request:

* :func:`get_auth_service` — returns the shared service instance
* :func:`get_current_user` — decodes the ``Bearer`` token and returns
  the authenticated :class:`~src.auth.schemas.UserResponse`
* :func:`require_roles` — factory that produces a dependency checking
  the user's role against an allow-list
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.auth.config import load_auth_settings
from src.auth.database import AuthDatabase
from src.auth.rate_limiter import SlidingWindowRateLimiter
from src.auth.schemas import UserResponse
from src.auth.service import AuthService, AuthServiceError

settings = load_auth_settings()
database = AuthDatabase(settings.auth_db_path)
rate_limiter = SlidingWindowRateLimiter(
    max_attempts=settings.rate_limit_max_attempts,
    window_seconds=settings.rate_limit_window_seconds,
)
auth_service = AuthService(
    database=database,
    settings=settings,
    rate_limiter=rate_limiter,
)
http_bearer = HTTPBearer(auto_error=False)


def get_auth_service() -> AuthService:
    return auth_service



def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
    service: AuthService = Depends(get_auth_service),
) -> UserResponse:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    try:
        return service.get_current_user(credentials.credentials)
    except AuthServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc



def require_roles(*roles: str):
    def dependency(current_user: UserResponse = Depends(get_current_user)) -> UserResponse:
        if current_user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions.")
        return current_user

    return dependency

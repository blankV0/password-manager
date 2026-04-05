"""
Authentication settings loaded from environment variables.

Every tuneable — JWT secret, token TTLs, lockout thresholds, rate-limit
windows — is read from ``os.environ`` at import time and frozen into an
immutable :class:`AuthSettings` dataclass.  This makes configuration
explicit, testable, and impossible to mutate at runtime.

Directories (``data/``, ``logs/``) are created eagerly so that the
application never fails on a missing folder at an inconvenient time.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

if getattr(sys, "frozen", False):
    APP_ROOT = Path(sys.executable).resolve().parent
else:
    APP_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = APP_ROOT / "data"
LOG_DIR = APP_ROOT / "logs"
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class AuthSettings:
    auth_db_path: Path
    auth_log_file: Path
    jwt_secret: str
    jwt_algorithm: str
    access_token_ttl_seconds: int
    refresh_token_ttl_seconds: int
    issuer: str
    audience: str
    login_max_failures: int
    login_lockout_seconds: int
    rate_limit_window_seconds: int
    rate_limit_max_attempts: int
    password_min_length: int


_DEFAULT_JWT_SECRET = os.getenv("AUTH_JWT_SECRET", "change-me-in-production")


def load_auth_settings() -> AuthSettings:
    return AuthSettings(
        auth_db_path=Path(os.getenv("AUTH_DB_PATH", DATA_DIR / "auth.db")),
        auth_log_file=Path(os.getenv("AUTH_LOG_FILE", LOG_DIR / "auth.log")),
        jwt_secret=_DEFAULT_JWT_SECRET,
        jwt_algorithm=os.getenv("AUTH_JWT_ALGORITHM", "HS256"),
        access_token_ttl_seconds=int(os.getenv("AUTH_ACCESS_TOKEN_TTL_SECONDS", "900")),
        refresh_token_ttl_seconds=int(os.getenv("AUTH_REFRESH_TOKEN_TTL_SECONDS", str(60 * 60 * 24 * 7))),
        issuer=os.getenv("AUTH_ISSUER", "password-manager-auth"),
        audience=os.getenv("AUTH_AUDIENCE", "password-manager-clients"),
        login_max_failures=int(os.getenv("AUTH_LOGIN_MAX_FAILURES", "5")),
        login_lockout_seconds=int(os.getenv("AUTH_LOGIN_LOCKOUT_SECONDS", "900")),
        rate_limit_window_seconds=int(os.getenv("AUTH_RATE_LIMIT_WINDOW_SECONDS", "300")),
        rate_limit_max_attempts=int(os.getenv("AUTH_RATE_LIMIT_MAX_ATTEMPTS", "10")),
        password_min_length=int(os.getenv("AUTH_PASSWORD_MIN_LENGTH", "12")),
    )

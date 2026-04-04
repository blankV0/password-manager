"""
JWT access-token and opaque refresh-token helpers.

**Access tokens** are short-lived JWTs (default 15 min) signed with
HS256.  They carry ``sub`` (user-id), ``role`` and standard claims
(``iss``, ``aud``, ``iat``, ``nbf``, ``exp``, ``jti``).

**Refresh tokens** are cryptographically random URL-safe strings.
Only their SHA-256 hash is stored in the database so that a database
leak does not compromise active sessions.
"""

from __future__ import annotations

import hashlib
import secrets
import time
from typing import Any, Dict

import jwt

from src.auth.config import AuthSettings



def create_access_token(*, settings: AuthSettings, user_id: str, email: str, role: str) -> tuple[str, int]:
    now = int(time.time())
    exp = now + settings.access_token_ttl_seconds
    payload: Dict[str, Any] = {
        "sub": user_id,
        "email": email,
        "role": role,
        "type": "access",
        "iss": settings.issuer,
        "aud": settings.audience,
        "iat": now,
        "nbf": now,
        "exp": exp,
        "jti": secrets.token_hex(16),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, settings.access_token_ttl_seconds



def decode_access_token(token: str, settings: AuthSettings) -> Dict[str, Any]:
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        audience=settings.audience,
        issuer=settings.issuer,
    )



def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)



def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

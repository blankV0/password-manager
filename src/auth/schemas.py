"""
Pydantic request / response models for the auth API.

Validation rules (min/max lengths, email format) are enforced here at
the serialisation boundary so that the service layer can trust its
inputs without redundant checks.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)
    username: Optional[str] = Field(default=None, min_length=3, max_length=30)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=32, max_length=512)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=32, max_length=512)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    username: Optional[str] = None
    role: str
    is_active: bool
    is_verified: bool
    must_change_password: bool = False


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserResponse


class MessageResponse(BaseModel):
    message: str


# ── Admin schemas ────────────────────────────────────────────────────────────


class AdminSetActiveRequest(BaseModel):
    email: EmailStr
    active: bool


class AdminResetPasswordRequest(BaseModel):
    email: EmailStr
    new_password: str = Field(min_length=12, max_length=256)


class AdminDeleteUserRequest(BaseModel):
    email: EmailStr


class AdminMessageResponse(BaseModel):
    """Resposta admin com campo 'ok' para compatibilidade com _api_post."""
    ok: bool = True
    message: str


class AdminUserItem(BaseModel):
    """Representação resumida de um utilizador para o painel admin."""
    id: str
    email: str
    username: Optional[str] = None
    role: str
    active: bool
    is_verified: bool
    created_at: str  # ISO-8601


class AdminUsersResponse(BaseModel):
    ok: bool = True
    users: list[AdminUserItem]


class AdminLogItem(BaseModel):
    timestamp: str
    event_type: str
    email: str
    success: bool
    ip_address: Optional[str] = None
    details: Optional[str] = None


class AdminLogsResponse(BaseModel):
    ok: bool = True
    logs: list[AdminLogItem]

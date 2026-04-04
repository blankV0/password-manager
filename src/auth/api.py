"""
REST endpoints for the authentication module.

Every route delegates to :class:`~src.auth.service.AuthService`; the thin
controller layer is responsible **only** for HTTP concerns (status codes,
request/response serialisation, extracting client context).

Routes
------
POST /auth/register        — create a new user account
POST /auth/login           — authenticate and receive JWT + refresh token
POST /auth/refresh         — rotate refresh token (with reuse detection)
POST /auth/logout          — revoke the current refresh token
GET  /auth/me              — return the authenticated user profile
POST /auth/change-password — change password (requires current password)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from src.auth.dependencies import get_auth_service, get_current_user, require_roles
from src.auth.schemas import (
    AdminLogsResponse,
    AdminMessageResponse,
    AdminResetPasswordRequest,
    AdminSetActiveRequest,
    AdminUsersResponse,
    ChangePasswordRequest,
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from src.auth.service import AuthContext, AuthService, AuthServiceError

router = APIRouter(prefix="/auth", tags=["auth"])



def _build_context(request: Request) -> AuthContext:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    client_ip = forwarded_for.split(",")[0].strip() if forwarded_for else (request.client.host if request.client else "unknown")
    user_agent = request.headers.get("user-agent", "unknown")
    return AuthContext(ip_address=client_ip, user_agent=user_agent)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
) -> UserResponse:
    try:
        return service.register(payload, _build_context(request))
    except AuthServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    try:
        return service.login(payload, _build_context(request))
    except AuthServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    payload: RefreshRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    try:
        return service.refresh(payload.refresh_token, _build_context(request))
    except AuthServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/logout", response_model=MessageResponse)
def logout(
    payload: LogoutRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    service.logout(payload.refresh_token, _build_context(request))
    return MessageResponse(message="Logged out successfully.")


@router.get("/me", response_model=UserResponse)
def me(current_user: UserResponse = Depends(get_current_user)) -> UserResponse:
    return current_user


@router.post("/change-password", response_model=MessageResponse)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    """Altera a password do utilizador autenticado."""
    try:
        service.change_password(current_user.id, payload, _build_context(request))
        return MessageResponse(message="Password changed successfully.")
    except AuthServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


# ═════════════════════════════════════════════════════════════════════════════
# ADMIN ENDPOINTS — apenas acessíveis a utilizadores com role=admin
# ═════════════════════════════════════════════════════════════════════════════


@router.post("/admin/users", response_model=AdminUsersResponse)
def admin_list_users(
    request: Request,
    admin: UserResponse = Depends(require_roles("admin")),
    service: AuthService = Depends(get_auth_service),
) -> AdminUsersResponse:
    """Lista todos os utilizadores registados."""
    users = service.admin_list_users()
    return AdminUsersResponse(users=users)


@router.post("/admin/user/active", response_model=AdminMessageResponse)
def admin_set_active(
    payload: AdminSetActiveRequest,
    request: Request,
    admin: UserResponse = Depends(require_roles("admin")),
    service: AuthService = Depends(get_auth_service),
) -> AdminMessageResponse:
    """Ativa ou desativa a conta de um utilizador."""
    try:
        service.admin_set_active(payload.email, payload.active, _build_context(request))
        action = "ativada" if payload.active else "desativada"
        return AdminMessageResponse(message=f"Conta {action} com sucesso.")
    except AuthServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/admin/user/reset-password", response_model=AdminMessageResponse)
def admin_reset_password(
    payload: AdminResetPasswordRequest,
    request: Request,
    admin: UserResponse = Depends(require_roles("admin")),
    service: AuthService = Depends(get_auth_service),
) -> AdminMessageResponse:
    """Redefine a password de um utilizador."""
    try:
        service.admin_reset_password(payload.email, payload.new_password, _build_context(request))
        return AdminMessageResponse(message="Password redefinida com sucesso.")
    except AuthServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/admin/logs", response_model=AdminLogsResponse)
def admin_get_logs(
    request: Request,
    admin: UserResponse = Depends(require_roles("admin")),
    service: AuthService = Depends(get_auth_service),
) -> AdminLogsResponse:
    """Devolve os últimos eventos de autenticação."""
    logs = service.admin_get_logs()
    return AdminLogsResponse(logs=logs)

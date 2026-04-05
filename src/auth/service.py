"""
Core authentication business logic.

:class:`AuthService` orchestrates every auth operation — registration,
login, token refresh, logout and password change — while enforcing:

* **Rate limiting** via :class:`~src.auth.rate_limiter.SlidingWindowRateLimiter`
* **Account lockout** after N consecutive failures
* **Constant-time responses** on invalid credentials (``time.sleep``)
* **Transparent Argon2id rehashing** when cost parameters change
* **Refresh-token rotation** with automatic reuse detection
* **Full audit trail** written to both SQLite and structured logs

The service never raises raw exceptions to the caller; it uses
:class:`AuthServiceError` with an explicit HTTP status code so that the
API layer can translate it directly.
"""

from __future__ import annotations

import re
import secrets
import sqlite3
import time
from dataclasses import dataclass
from typing import Optional

import jwt

from src.auth.config import AuthSettings
from src.auth.database import AuthDatabase
from src.auth.passwords import hash_password, needs_rehash, verify_password
from src.auth.rate_limiter import SlidingWindowRateLimiter
from src.auth.schemas import (
    AdminLogItem,
    AdminUserItem,
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from src.auth.tokens import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_refresh_token,
)
from src.utils.logging_config import configure_logging
from src.utils.security_validator import SecurityValidator

USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9._-]{3,30}$")
SPECIAL_PATTERN = re.compile(r"[!@#$%^&*()_+\-=\[\]{};':\",.<>/?]")


class AuthServiceError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


@dataclass(frozen=True)
class AuthContext:
    ip_address: str
    user_agent: str


class AuthService:
    def __init__(
        self,
        *,
        database: AuthDatabase,
        settings: AuthSettings,
        rate_limiter: SlidingWindowRateLimiter,
    ):
        self.database = database
        self.settings = settings
        self.rate_limiter = rate_limiter
        self.logger = configure_logging(
            settings.auth_log_file,
            logger_name="auth",
            propagate=False,
        )

    def register(self, payload: RegisterRequest, context: AuthContext) -> UserResponse:
        email = self._normalize_email(payload.email)
        username = payload.username.strip() if payload.username else None
        self._validate_password_strength(payload.password)
        if username and not USERNAME_PATTERN.fullmatch(username):
            raise AuthServiceError(400, "Registration could not be completed.")

        now = int(time.time())
        user_id = secrets.token_hex(16)
        password_hash = hash_password(payload.password)

        try:
            with self.database.connection() as conn:
                existing = conn.execute(
                    "SELECT id FROM users WHERE email = ? OR (username IS NOT NULL AND username = ?)",
                    (email, username),
                ).fetchone()
                if existing:
                    self._record_event(
                        conn,
                        user_id=None,
                        email_hint=SecurityValidator.mask_email(email),
                        event_type="register_duplicate",
                        success=False,
                        context=context,
                        detail="duplicate_identity",
                    )
                    raise AuthServiceError(400, "Registration could not be completed.")

                conn.execute(
                    """
                    INSERT INTO users (
                        id, email, username, password_hash, role, is_active, is_verified,
                        failed_login_attempts, lock_until, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, 'user', 1, 0, 0, 0, ?, ?)
                    """,
                    (user_id, email, username, password_hash, now, now),
                )
                self._record_event(
                    conn,
                    user_id=user_id,
                    email_hint=SecurityValidator.mask_email(email),
                    event_type="register",
                    success=True,
                    context=context,
                    detail="user_registered",
                )
        except sqlite3.IntegrityError:
            raise AuthServiceError(400, "Registration could not be completed.")

        return UserResponse(
            id=user_id,
            email=email,
            username=username,
            role="user",
            is_active=True,
            is_verified=False,
        )

    def login(self, payload: LoginRequest, context: AuthContext) -> TokenResponse:
        email = self._normalize_email(payload.email)
        rate_limit_key = f"{context.ip_address}:{email}"
        allowed, retry_after = self.rate_limiter.allow(rate_limit_key)
        if not allowed:
            self.logger.warning(
                "[AUTH] Rate limit exceeded email=%s ip=%s retry_after=%s",
                SecurityValidator.mask_email(email),
                context.ip_address,
                retry_after,
            )
            raise AuthServiceError(429, "Too many login attempts. Try again later.")

        now = int(time.time())
        with self.database.connection() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE email = ?",
                (email,),
            ).fetchone()

            if not row:
                self.rate_limiter.register_failure(rate_limit_key)
                self._record_event(
                    conn,
                    user_id=None,
                    email_hint=SecurityValidator.mask_email(email),
                    event_type="login",
                    success=False,
                    context=context,
                    detail="invalid_credentials",
                )
                time.sleep(0.35)
                raise AuthServiceError(401, "Invalid email or password.")

            if not row["is_active"]:
                self.rate_limiter.register_failure(rate_limit_key)
                self._record_event(
                    conn,
                    user_id=row["id"],
                    email_hint=SecurityValidator.mask_email(email),
                    event_type="login",
                    success=False,
                    context=context,
                    detail="inactive_account",
                )
                raise AuthServiceError(401, "Invalid email or password.")

            if row["lock_until"] and row["lock_until"] > now:
                self.rate_limiter.register_failure(rate_limit_key)
                self._record_event(
                    conn,
                    user_id=row["id"],
                    email_hint=SecurityValidator.mask_email(email),
                    event_type="login_locked",
                    success=False,
                    context=context,
                    detail="account_locked",
                )
                raise AuthServiceError(429, "Too many login attempts. Try again later.")

            if not verify_password(row["password_hash"], payload.password):
                self.rate_limiter.register_failure(rate_limit_key)
                failed_attempts = int(row["failed_login_attempts"]) + 1
                lock_until = (
                    now + self.settings.login_lockout_seconds
                    if failed_attempts >= self.settings.login_max_failures
                    else 0
                )
                conn.execute(
                    "UPDATE users SET failed_login_attempts = ?, lock_until = ?, updated_at = ? WHERE id = ?",
                    (failed_attempts, lock_until, now, row["id"]),
                )
                self._record_event(
                    conn,
                    user_id=row["id"],
                    email_hint=SecurityValidator.mask_email(email),
                    event_type="login",
                    success=False,
                    context=context,
                    detail="invalid_credentials",
                )
                time.sleep(0.35)
                raise AuthServiceError(401, "Invalid email or password.")

            password_hash = row["password_hash"]
            if needs_rehash(password_hash):
                password_hash = hash_password(payload.password)
                conn.execute(
                    "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                    (password_hash, now, row["id"]),
                )

            conn.execute(
                "UPDATE users SET failed_login_attempts = 0, lock_until = 0, last_login_at = ?, updated_at = ? WHERE id = ?",
                (now, now, row["id"]),
            )

            access_token, expires_in = create_access_token(
                settings=self.settings,
                user_id=row["id"],
                email=row["email"],
                role=row["role"],
            )
            refresh_token = generate_refresh_token()
            refresh_token_id = secrets.token_hex(16)
            conn.execute(
                """
                INSERT INTO refresh_tokens (
                    id, user_id, token_hash, expires_at, revoked_at, replaced_by_token_id,
                    ip_address, user_agent, created_at
                ) VALUES (?, ?, ?, ?, NULL, NULL, ?, ?, ?)
                """,
                (
                    refresh_token_id,
                    row["id"],
                    hash_refresh_token(refresh_token),
                    now + self.settings.refresh_token_ttl_seconds,
                    context.ip_address,
                    context.user_agent,
                    now,
                ),
            )
            self._record_event(
                conn,
                user_id=row["id"],
                email_hint=SecurityValidator.mask_email(email),
                event_type="login",
                success=True,
                context=context,
                detail="login_success",
            )

        self.rate_limiter.reset(rate_limit_key)
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            user=self._build_user_response(row),
        )

    def refresh(self, refresh_token: str, context: AuthContext) -> TokenResponse:
        now = int(time.time())
        token_hash = hash_refresh_token(refresh_token)
        with self.database.connection() as conn:
            row = conn.execute(
                """
                SELECT rt.*, u.email, u.username, u.role, u.is_active, u.is_verified
                FROM refresh_tokens rt
                JOIN users u ON u.id = rt.user_id
                WHERE rt.token_hash = ?
                """,
                (token_hash,),
            ).fetchone()
            if not row:
                raise AuthServiceError(401, "Invalid refresh token.")

            if row["revoked_at"]:
                self._revoke_all_user_tokens(conn, row["user_id"], now)
                self._record_event(
                    conn,
                    user_id=row["user_id"],
                    email_hint=SecurityValidator.mask_email(row["email"]),
                    event_type="refresh_reuse_detected",
                    success=False,
                    context=context,
                    detail="reused_refresh_token",
                )
                raise AuthServiceError(401, "Invalid refresh token.")

            if not row["is_active"] or row["expires_at"] <= now:
                conn.execute(
                    "UPDATE refresh_tokens SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL",
                    (now, row["id"]),
                )
                raise AuthServiceError(401, "Invalid refresh token.")

            new_refresh_token = generate_refresh_token()
            new_refresh_token_id = secrets.token_hex(16)
            conn.execute(
                """
                INSERT INTO refresh_tokens (
                    id, user_id, token_hash, expires_at, revoked_at, replaced_by_token_id,
                    ip_address, user_agent, created_at
                ) VALUES (?, ?, ?, ?, NULL, NULL, ?, ?, ?)
                """,
                (
                    new_refresh_token_id,
                    row["user_id"],
                    hash_refresh_token(new_refresh_token),
                    now + self.settings.refresh_token_ttl_seconds,
                    context.ip_address,
                    context.user_agent,
                    now,
                ),
            )
            conn.execute(
                "UPDATE refresh_tokens SET revoked_at = ?, replaced_by_token_id = ? WHERE id = ?",
                (now, new_refresh_token_id, row["id"]),
            )

            access_token, expires_in = create_access_token(
                settings=self.settings,
                user_id=row["user_id"],
                email=row["email"],
                role=row["role"],
            )
            self._record_event(
                conn,
                user_id=row["user_id"],
                email_hint=SecurityValidator.mask_email(row["email"]),
                event_type="refresh",
                success=True,
                context=context,
                detail="token_rotated",
            )

        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            expires_in=expires_in,
            user=UserResponse(
                id=row["user_id"],
                email=row["email"],
                username=row["username"],
                role=row["role"],
                is_active=bool(row["is_active"]),
                is_verified=bool(row["is_verified"]),
            ),
        )

    def logout(self, refresh_token: str, context: AuthContext) -> None:
        now = int(time.time())
        token_hash = hash_refresh_token(refresh_token)
        with self.database.connection() as conn:
            row = conn.execute(
                """
                SELECT rt.id, rt.user_id, u.email
                FROM refresh_tokens rt
                LEFT JOIN users u ON u.id = rt.user_id
                WHERE rt.token_hash = ?
                """,
                (token_hash,),
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE refresh_tokens SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL",
                    (now, row["id"]),
                )
                self._record_event(
                    conn,
                    user_id=row["user_id"],
                    email_hint=SecurityValidator.mask_email(row["email"]) if row["email"] else None,
                    event_type="logout",
                    success=True,
                    context=context,
                    detail="refresh_token_revoked",
                )

    def get_current_user(self, access_token: str) -> UserResponse:
        try:
            payload = decode_access_token(access_token, self.settings)
        except jwt.PyJWTError as exc:
            raise AuthServiceError(401, "Invalid access token.") from exc

        user_id = payload.get("sub")
        if not user_id:
            raise AuthServiceError(401, "Invalid access token.")

        with self.database.connection() as conn:
            row = conn.execute(
                "SELECT id, email, username, role, is_active, is_verified FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            if not row or not row["is_active"]:
                raise AuthServiceError(401, "Invalid access token.")
            return self._build_user_response(row)

    def _revoke_all_user_tokens(self, conn: sqlite3.Connection, user_id: str, now: int) -> None:
        conn.execute(
            "UPDATE refresh_tokens SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
            (now, user_id),
        )

    def _build_user_response(self, row: sqlite3.Row) -> UserResponse:
        return UserResponse(
            id=row["id"],
            email=row["email"],
            username=row["username"],
            role=row["role"],
            is_active=bool(row["is_active"]),
            is_verified=bool(row["is_verified"]),
            must_change_password=bool(row["must_change_password"]) if "must_change_password" in row.keys() else False,
        )

    def change_password(
        self, user_id: str, payload: ChangePasswordRequest, context: AuthContext
    ) -> None:
        """Altera a password do utilizador atual."""
        self._validate_password_strength(payload.new_password)
        now = int(time.time())

        with self.database.connection() as conn:
            row = conn.execute(
                "SELECT id, email, password_hash FROM users WHERE id = ? AND is_active = 1",
                (user_id,),
            ).fetchone()
            if not row:
                raise AuthServiceError(401, "Invalid user.")

            if not verify_password(row["password_hash"], payload.current_password):
                self._record_event(
                    conn,
                    user_id=user_id,
                    email_hint=SecurityValidator.mask_email(row["email"]),
                    event_type="change_password",
                    success=False,
                    context=context,
                    detail="invalid_current_password",
                )
                raise AuthServiceError(400, "Current password is incorrect.")

            new_hash = hash_password(payload.new_password)
            conn.execute(
                "UPDATE users SET password_hash = ?, must_change_password = 0, updated_at = ? WHERE id = ?",
                (new_hash, now, user_id),
            )
            # Revogar TODOS os refresh tokens (force re-login em todos os dispositivos)
            self._revoke_all_user_tokens(conn, user_id, now)
            self._record_event(
                conn,
                user_id=user_id,
                email_hint=SecurityValidator.mask_email(row["email"]),
                event_type="change_password",
                success=True,
                context=context,
                detail="password_changed",
            )

    def periodic_cleanup(self) -> dict:
        """Limpeza periódica de tokens expirados e eventos antigos."""
        tokens_removed = self.database.cleanup_expired_tokens()
        events_removed = self.database.cleanup_old_events()
        return {"tokens_removed": tokens_removed, "events_removed": events_removed}

    # ── Operações de administração ────────────────────────────────────

    def admin_list_users(self) -> list[AdminUserItem]:
        """Devolve todos os utilizadores registados."""
        from datetime import datetime, timezone

        with self.database.connection() as conn:
            rows = conn.execute(
                "SELECT id, email, username, role, is_active, is_verified, created_at FROM users ORDER BY created_at DESC"
            ).fetchall()

        users: list[AdminUserItem] = []
        for row in rows:
            created_ts = int(row["created_at"])
            created_iso = datetime.fromtimestamp(created_ts, tz=timezone.utc).isoformat()
            users.append(
                AdminUserItem(
                    id=row["id"],
                    email=row["email"],
                    username=row["username"],
                    role=row["role"],
                    active=bool(row["is_active"]),
                    is_verified=bool(row["is_verified"]),
                    created_at=created_iso,
                )
            )
        return users

    def admin_set_active(self, email: str, active: bool, context: AuthContext) -> None:
        """Ativa ou desativa a conta de um utilizador."""
        email = email.strip().lower()
        now = int(time.time())

        with self.database.connection() as conn:
            row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if not row:
                raise AuthServiceError(404, "Utilizador não encontrado.")

            conn.execute(
                "UPDATE users SET is_active = ?, updated_at = ? WHERE email = ?",
                (1 if active else 0, now, email),
            )
            self._record_event(
                conn,
                user_id=row["id"],
                email_hint=SecurityValidator.mask_email(email),
                event_type="admin_set_active",
                success=True,
                context=context,
                detail=f"active={'true' if active else 'false'}",
            )

        if not active:
            # Revogar todos os tokens do utilizador desativado
            with self.database.connection() as conn:
                self._revoke_all_user_tokens(conn, row["id"], now)

    def admin_reset_password(self, email: str, new_password: str, context: AuthContext) -> None:
        """Redefine a password de um utilizador (apenas admin)."""
        email = email.strip().lower()
        self._validate_password_strength(new_password)
        now = int(time.time())
        new_hash = hash_password(new_password)

        with self.database.connection() as conn:
            row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if not row:
                raise AuthServiceError(404, "Utilizador não encontrado.")

            conn.execute(
                "UPDATE users SET password_hash = ?, must_change_password = 1, updated_at = ? WHERE email = ?",
                (new_hash, now, email),
            )
            self._revoke_all_user_tokens(conn, row["id"], now)
            self._record_event(
                conn,
                user_id=row["id"],
                email_hint=SecurityValidator.mask_email(email),
                event_type="admin_reset_password",
                success=True,
                context=context,
                detail="password_reset_by_admin",
            )

    def admin_get_logs(self, limit: int = 200) -> list[AdminLogItem]:
        """Devolve os últimos N eventos de autenticação."""
        from datetime import datetime, timezone

        with self.database.connection() as conn:
            rows = conn.execute(
                "SELECT email_hint, event_type, success, ip_address, detail, created_at "
                "FROM auth_events ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()

        logs: list[AdminLogItem] = []
        for row in rows:
            ts = int(row["created_at"])
            ts_iso = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
            logs.append(
                AdminLogItem(
                    timestamp=ts_iso,
                    event_type=row["event_type"],
                    email=row["email_hint"] or "—",
                    success=bool(row["success"]),
                    ip_address=row["ip_address"],
                    details=row["detail"],
                )
            )
        return logs

    def _record_event(
        self,
        conn: sqlite3.Connection,
        *,
        user_id: Optional[str],
        email_hint: Optional[str],
        event_type: str,
        success: bool,
        context: AuthContext,
        detail: str,
    ) -> None:
        created_at = int(time.time())
        conn.execute(
            """
            INSERT INTO auth_events (
                user_id, email_hint, event_type, success, ip_address, user_agent, detail, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                email_hint,
                event_type,
                1 if success else 0,
                context.ip_address,
                context.user_agent[:255],
                detail,
                created_at,
            ),
        )
        self.logger.info(
            "[AUTH] event=%s success=%s user_id=%s email=%s ip=%s detail=%s",
            event_type,
            success,
            user_id or "anonymous",
            email_hint or "n/a",
            context.ip_address,
            detail,
        )

    def _normalize_email(self, email: str) -> str:
        return email.strip().lower()

    def _validate_password_strength(self, password: str) -> None:
        if len(password) < self.settings.password_min_length:
            raise AuthServiceError(400, f"Password must be at least {self.settings.password_min_length} characters long.")
        if not any(char.islower() for char in password):
            raise AuthServiceError(400, "Password must contain at least one lowercase letter.")
        if not any(char.isupper() for char in password):
            raise AuthServiceError(400, "Password must contain at least one uppercase letter.")
        if not any(char.isdigit() for char in password):
            raise AuthServiceError(400, "Password must contain at least one number.")
        if not SPECIAL_PATTERN.search(password):
            raise AuthServiceError(400, "Password must contain at least one special character.")
        weak_patterns = ("password", "qwerty", "admin", "letmein", "welcome")
        password_lower = password.lower()
        for pattern in weak_patterns:
            if pattern in password_lower:
                raise AuthServiceError(400, "Password contains a weak or common pattern.")

    def admin_delete_user(self, email: str, context: "AuthContext") -> None:
        """Admin: delete user account and all associated data."""
        with self.database.connection() as conn:
            user = conn.execute("SELECT id, role FROM users WHERE email = ?", (email,)).fetchone()
            if not user:
                raise AuthServiceError(404, "Utilizador nao encontrado.")
            if user["role"] == "admin":
                raise AuthServiceError(400, "Nao e possivel eliminar uma conta admin.")
            user_id = user["id"]
            self._record_event(
                conn,
                user_id=user_id,
                email_hint=SecurityValidator.mask_email(email),
                event_type="admin_delete_user",
                success=True,
                context=context,
                detail="Deleted user " + email,
            )
            conn.execute("DELETE FROM vault_entries WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM vault_keys WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM email_verifications WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM refresh_tokens WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM auth_events WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))

    def delete_own_account(self, user_id: str, context: "AuthContext") -> None:
        """User deletes their own account and all associated data."""
        with self.database.connection() as conn:
            user = conn.execute("SELECT id, email, role FROM users WHERE id = ?", (user_id,)).fetchone()
            if not user:
                raise AuthServiceError(404, "Utilizador nao encontrado.")
            if user["role"] == "admin":
                raise AuthServiceError(400, "Contas admin nao podem ser auto-eliminadas.")
            self._record_event(
                conn,
                user_id=user_id,
                email_hint=SecurityValidator.mask_email(user["email"]),
                event_type="self_delete_account",
                success=True,
                context=context,
                detail="User deleted own account",
            )
            conn.execute("DELETE FROM vault_entries WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM vault_keys WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM email_verifications WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM refresh_tokens WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM auth_events WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))

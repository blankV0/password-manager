#!/usr/bin/env python3
"""
Server-side patch: adds email verification flow.

Changes:
1. database.py — add email_verifications table + migration
2. schemas.py — add RegisterResponse with verification_token, VerifyEmailRequest
3. service.py — generate verification token on register, verify_email method, resend method
4. api.py — GET /auth/verify-email, POST /auth/resend-verification
5. email_service.py — NEW: server-side email sending (SMTP)
"""

import textwrap, pathlib, sys

BASE = pathlib.Path("/home/blankroot/password-manager")

# ═══════════════════════════════════════════════════════════════════════════
# 1. email_service.py — server-side email sending
# ═══════════════════════════════════════════════════════════════════════════
(BASE / "src" / "auth" / "email_service.py").write_text(textwrap.dedent('''\
    """
    Server-side email service for sending verification emails.
    Uses SMTP (Gmail) to send HTML emails.
    """

    from __future__ import annotations

    import logging
    import os
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    logger = logging.getLogger(__name__)

    _SENDER = os.getenv("EMAIL_SENDER", "")
    _PASSWORD = os.getenv("EMAIL_PASSWORD", "")
    _SMTP_SERVER = os.getenv("EMAIL_SMTP_SERVER", "smtp.gmail.com")
    _SMTP_PORT = int(os.getenv("EMAIL_SMTP_PORT", "465"))
    _BASE_URL = os.getenv("EMAIL_VERIFICATION_BASE_URL", "https://localhost")


    def send_verification_email(email: str, token: str, username: str | None = None) -> bool:
        """Send a verification email with a clickable link. Returns True on success."""
        if not _SENDER or not _PASSWORD:
            logger.warning("[EMAIL] SMTP not configured — skipping verification email to %s", email)
            return False

        display_name = username or email.split("@")[0]
        verify_url = f"{_BASE_URL}/auth/verify-email?token={token}"

        html = f"""
        <html>
        <body style="font-family:Arial,sans-serif;background:#f5f5f5;padding:20px">
          <div style="max-width:500px;margin:0 auto;background:#fff;padding:30px;border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,.1)">
            <h2 style="color:#2C2F33;margin-top:0">Bem-vindo, {display_name}! 👋</h2>
            <p style="color:#666;font-size:14px">
              Obrigado por se registar no <strong>Password Manager</strong>.
            </p>
            <p style="color:#666;font-size:14px">
              Para completar o seu registo, clique no botão abaixo:
            </p>
            <div style="text-align:center;margin:30px 0">
              <a href="{verify_url}"
                 style="background:#22c55e;color:#fff;padding:12px 30px;text-decoration:none;border-radius:5px;font-weight:bold;display:inline-block">
                ✅ Verificar Email
              </a>
            </div>
            <p style="color:#999;font-size:12px;border-top:1px solid #eee;padding-top:20px">
              Ou copie este link:<br/>
              <code style="background:#f5f5f5;padding:8px;border-radius:3px;word-break:break-all">{verify_url}</code>
            </p>
            <p style="color:#999;font-size:12px">Este link expira em 24 horas.</p>
          </div>
        </body>
        </html>
        """

        text = f"Bem-vindo, {display_name}!\\nPara verificar o seu email, aceda: {verify_url}\\nExpira em 24 horas."

        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Verificar o seu Email - Password Manager"
        msg["From"] = _SENDER
        msg["To"] = email
        msg.attach(MIMEText(text, "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))

        try:
            if _SMTP_PORT == 465:
                with smtplib.SMTP_SSL(_SMTP_SERVER, _SMTP_PORT) as srv:
                    srv.login(_SENDER, _PASSWORD)
                    srv.send_message(msg)
            else:
                with smtplib.SMTP(_SMTP_SERVER, _SMTP_PORT) as srv:
                    srv.starttls()
                    srv.login(_SENDER, _PASSWORD)
                    srv.send_message(msg)
            logger.info("[EMAIL] Verification email sent to %s", email)
            return True
        except Exception as exc:
            logger.error("[EMAIL] Failed to send to %s: %s", email, exc)
            return False
''').lstrip())

print("[OK] email_service.py created")

# ═══════════════════════════════════════════════════════════════════════════
# 2. database.py — add email_verifications table
# ═══════════════════════════════════════════════════════════════════════════
db_path = BASE / "src" / "auth" / "database.py"
db_code = db_path.read_text()

# Add the table after vault_entries index
insert_after = 'CREATE INDEX IF NOT EXISTS idx_vault_entries_user_id ON vault_entries(user_id);'
new_table = '''

                -- ── Email verification tokens ────────────────────────
                CREATE TABLE IF NOT EXISTS email_verifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    token TEXT NOT NULL UNIQUE,
                    expires_at INTEGER NOT NULL,
                    used_at INTEGER,
                    created_at INTEGER NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_email_verif_token ON email_verifications(token);
                CREATE INDEX IF NOT EXISTS idx_email_verif_user ON email_verifications(user_id);'''

if 'email_verifications' not in db_code:
    db_code = db_code.replace(insert_after, insert_after + new_table)
    db_path.write_text(db_code)
    print("[OK] database.py updated — email_verifications table added")
else:
    print("[SKIP] database.py already has email_verifications")


# ═══════════════════════════════════════════════════════════════════════════
# 3. schemas.py — add RegisterResponse, verify/resend schemas
# ═══════════════════════════════════════════════════════════════════════════
schema_path = BASE / "src" / "auth" / "schemas.py"
schema_code = schema_path.read_text()

# Add RegisterResponse after UserResponse
if "RegisterResponse" not in schema_code:
    ur_end = schema_code.find("class TokenResponse")
    schema_code = schema_code[:ur_end] + '''class RegisterResponse(BaseModel):
    """Response after successful registration — includes verification token."""
    id: str
    email: EmailStr
    username: Optional[str] = None
    role: str
    is_active: bool
    is_verified: bool
    must_change_password: bool = False
    verification_token: Optional[str] = None


''' + schema_code[ur_end:]
    schema_path.write_text(schema_code)
    print("[OK] schemas.py updated — RegisterResponse added")
else:
    print("[SKIP] schemas.py already has RegisterResponse")


# ═══════════════════════════════════════════════════════════════════════════
# 4. service.py — generate verification token, verify_email, resend
# ═══════════════════════════════════════════════════════════════════════════
svc_path = BASE / "src" / "auth" / "service.py"
svc_code = svc_path.read_text()

# 4a. Change register return type and add token generation
if "RegisterResponse" not in svc_code:
    # Import RegisterResponse
    svc_code = svc_code.replace(
        "from src.auth.schemas import (",
        "from src.auth.schemas import (\n    RegisterResponse,"
    )

    # Change register return type
    svc_code = svc_code.replace(
        "def register(self, payload: RegisterRequest, context: AuthContext) -> UserResponse:",
        "def register(self, payload: RegisterRequest, context: AuthContext) -> RegisterResponse:"
    )

    # Replace the return UserResponse(...) block at end of register with token generation
    old_return = '''        return UserResponse(
            id=user_id,
            email=email,
            username=username,
            role="user",
            is_active=True,
            is_verified=False,
        )'''

    new_return = '''        # Generate email verification token
        verification_token = secrets.token_urlsafe(32)
        token_expiry = now + 86400  # 24 hours

        with self.database.connection() as conn:
            conn.execute(
                "INSERT INTO email_verifications (user_id, token, expires_at, created_at) VALUES (?, ?, ?, ?)",
                (user_id, verification_token, token_expiry, now),
            )

        # Send verification email (best-effort, don't block registration)
        try:
            from src.auth.email_service import send_verification_email
            send_verification_email(email, verification_token, username)
        except Exception as exc:
            self.logger.warning("[AUTH] Failed to send verification email: %s", exc)

        return RegisterResponse(
            id=user_id,
            email=email,
            username=username,
            role="user",
            is_active=True,
            is_verified=False,
            verification_token=verification_token,
        )'''

    svc_code = svc_code.replace(old_return, new_return)

    # Add verify_email and resend_verification methods before _revoke_all_user_tokens
    verify_methods = '''
    def verify_email(self, token: str, context: AuthContext) -> str:
        """Verify email using token. Returns success HTML page."""
        now = int(time.time())
        with self.database.connection() as conn:
            row = conn.execute(
                "SELECT ev.id, ev.user_id, ev.expires_at, ev.used_at, u.email "
                "FROM email_verifications ev JOIN users u ON u.id = ev.user_id "
                "WHERE ev.token = ?",
                (token,),
            ).fetchone()

            if not row:
                raise AuthServiceError(400, "Token de verificação inválido.")

            if row["used_at"]:
                return "already_verified"

            if row["expires_at"] < now:
                raise AuthServiceError(400, "Token expirado. Solicite um novo email de verificação.")

            conn.execute(
                "UPDATE email_verifications SET used_at = ? WHERE id = ?",
                (now, row["id"]),
            )
            conn.execute(
                "UPDATE users SET is_verified = 1, updated_at = ? WHERE id = ?",
                (now, row["user_id"]),
            )
            self._record_event(
                conn,
                user_id=row["user_id"],
                email_hint=SecurityValidator.mask_email(row["email"]),
                event_type="email_verified",
                success=True,
                context=context,
                detail="email_verified",
            )
        return "verified"

    def resend_verification(self, email: str, context: AuthContext) -> str:
        """Resend verification email. Returns new token."""
        email = self._normalize_email(email)
        now = int(time.time())

        with self.database.connection() as conn:
            row = conn.execute(
                "SELECT id, username, is_verified FROM users WHERE email = ?",
                (email,),
            ).fetchone()

            if not row:
                raise AuthServiceError(404, "Email não encontrado.")

            if row["is_verified"]:
                raise AuthServiceError(400, "Email já verificado.")

            # Invalidate old tokens
            conn.execute(
                "UPDATE email_verifications SET used_at = ? WHERE user_id = ? AND used_at IS NULL",
                (now, row["id"]),
            )

            # Generate new token
            token = secrets.token_urlsafe(32)
            conn.execute(
                "INSERT INTO email_verifications (user_id, token, expires_at, created_at) VALUES (?, ?, ?, ?)",
                (row["id"], token, now + 86400, now),
            )

        try:
            from src.auth.email_service import send_verification_email
            send_verification_email(email, token, row["username"])
        except Exception as exc:
            self.logger.warning("[AUTH] Failed to resend verification email: %s", exc)

        self._record_event(
            conn,
            user_id=row["id"],
            email_hint=SecurityValidator.mask_email(email),
            event_type="resend_verification",
            success=True,
            context=context,
            detail="verification_resent",
        )
        return token

    def check_email_verified(self, email: str) -> bool:
        """Check if a user's email is verified."""
        email = self._normalize_email(email)
        with self.database.connection() as conn:
            row = conn.execute(
                "SELECT is_verified FROM users WHERE email = ?",
                (email,),
            ).fetchone()
            if not row:
                return False
            return bool(row["is_verified"])

'''

    # Insert before _revoke_all_user_tokens
    svc_code = svc_code.replace(
        "    def _revoke_all_user_tokens(",
        verify_methods + "    def _revoke_all_user_tokens("
    )

    svc_path.write_text(svc_code)
    print("[OK] service.py updated — verify_email, resend_verification, check_email_verified added")
else:
    print("[SKIP] service.py already has RegisterResponse")


# ═══════════════════════════════════════════════════════════════════════════
# 5. api.py — add verify-email, resend-verification, check-verified endpoints
# ═══════════════════════════════════════════════════════════════════════════
api_path = BASE / "src" / "auth" / "api.py"
api_code = api_path.read_text()

if "verify-email" not in api_code:
    # Add RegisterResponse to imports
    api_code = api_code.replace(
        "    RegisterRequest,",
        "    RegisterRequest,\n    RegisterResponse,"
    )

    # Change register response_model
    api_code = api_code.replace(
        '@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)',
        '@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)'
    )
    api_code = api_code.replace(
        ") -> UserResponse:\n    try:\n        return service.register(",
        ") -> RegisterResponse:\n    try:\n        return service.register("
    )

    # Add new endpoints before the admin section
    new_endpoints = '''

# ── Email Verification Endpoints ──────────────────────────────────────────

from fastapi.responses import HTMLResponse


@router.get("/verify-email", response_class=HTMLResponse)
def verify_email(
    token: str,
    request: Request,
    service: AuthService = Depends(get_auth_service),
) -> HTMLResponse:
    """Verify email via link clicked in email."""
    try:
        result = service.verify_email(token, _build_context(request))
        if result == "already_verified":
            html = """<html><body style="font-family:Arial;text-align:center;padding:60px;background:#f5f5f5">
            <div style="max-width:400px;margin:0 auto;background:#fff;padding:40px;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,.1)">
            <h1 style="color:#22c55e">✅</h1>
            <h2 style="color:#333">Email já verificado!</h2>
            <p style="color:#666">O seu email já foi verificado anteriormente. Pode fechar esta página.</p>
            </div></body></html>"""
        else:
            html = """<html><body style="font-family:Arial;text-align:center;padding:60px;background:#f5f5f5">
            <div style="max-width:400px;margin:0 auto;background:#fff;padding:40px;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,.1)">
            <h1 style="color:#22c55e">✅</h1>
            <h2 style="color:#333">Email Verificado!</h2>
            <p style="color:#666">O seu email foi verificado com sucesso. Pode voltar à aplicação e iniciar sessão.</p>
            </div></body></html>"""
        return HTMLResponse(content=html)
    except AuthServiceError as exc:
        html = f"""<html><body style="font-family:Arial;text-align:center;padding:60px;background:#f5f5f5">
        <div style="max-width:400px;margin:0 auto;background:#fff;padding:40px;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,.1)">
        <h1 style="color:#ef4444">❌</h1>
        <h2 style="color:#333">Erro</h2>
        <p style="color:#666">{exc.message}</p>
        </div></body></html>"""
        return HTMLResponse(content=html, status_code=exc.status_code)


@router.post("/resend-verification")
def resend_verification(
    request: Request,
    email: str = None,
    service: AuthService = Depends(get_auth_service),
) -> dict:
    """Resend verification email."""
    if not email:
        raise HTTPException(status_code=400, detail="Email is required.")
    try:
        service.resend_verification(email, _build_context(request))
        return {"ok": True, "message": "Email de verificação reenviado."}
    except AuthServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/check-verified")
def check_verified(
    email: str,
    service: AuthService = Depends(get_auth_service),
) -> dict:
    """Check if email is verified (used by client polling)."""
    verified = service.check_email_verified(email)
    return {"verified": verified}


'''

    # Insert before admin section
    admin_marker = '# ═════════════════════════════════════════════════════════════════════════════'
    first_admin = api_code.find(admin_marker, api_code.find("ADMIN ENDPOINTS") - 200)
    if first_admin == -1:
        # Fallback: find the admin comment
        first_admin = api_code.find("# ADMIN ENDPOINTS")
        if first_admin > 0:
            # Go back to the separator line before it
            first_admin = api_code.rfind("\n\n", 0, first_admin)

    if first_admin > 0:
        api_code = api_code[:first_admin] + new_endpoints + api_code[first_admin:]

    api_path.write_text(api_code)
    print("[OK] api.py updated — verify-email, resend-verification, check-verified endpoints added")
else:
    print("[SKIP] api.py already has verify-email")


print("\n[DONE] All server files updated!")

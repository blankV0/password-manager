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

    text = f"Bem-vindo, {display_name}!\nPara verificar o seu email, aceda: {verify_url}\nExpira em 24 horas."

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

"""Serviço de verificação de email.
Envia emails de verificação com link e emails de confirmação de telemóvel.
"""

import smtplib
import logging
import uuid
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from src.config.settings import (
    EMAIL_SENDER,
    EMAIL_PASSWORD,
    EMAIL_SMTP_SERVER,
    EMAIL_SMTP_PORT,
    API_BASE_URL,
)

logger = logging.getLogger(__name__)


class EmailVerification:
    """Serviço de verificação de email."""

    @staticmethod
    def _build_email_message(email: str, subject: str, text_body: str, html_body: str) -> MIMEMultipart:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = EMAIL_SENDER
        msg["To"] = email
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))
        return msg

    @staticmethod
    def _send_email_message(email: str, message: MIMEMultipart) -> tuple:
        if not EMAIL_SENDER or not EMAIL_PASSWORD or not EMAIL_SMTP_SERVER:
            logger.warning("[AVISO] Email não configurado - pulando envio")
            return True, "Email não configurado no ambiente atual."

        try:
            if EMAIL_SMTP_PORT == 465:
                with smtplib.SMTP_SSL(EMAIL_SMTP_SERVER, EMAIL_SMTP_PORT) as server:
                    server.login(EMAIL_SENDER, EMAIL_PASSWORD)
                    server.send_message(message)
            else:
                with smtplib.SMTP(EMAIL_SMTP_SERVER, EMAIL_SMTP_PORT) as server:
                    server.starttls()
                    server.login(EMAIL_SENDER, EMAIL_PASSWORD)
                    server.send_message(message)

            logger.info(f"[OK] Email enviado para: {email}")
            return True, "Email enviado com sucesso!"
        except Exception as e:
            logger.error(f"[ERRO] Falha ao enviar email: {str(e)}")
            return False, f"Erro ao enviar email: {str(e)}"

    @staticmethod
    def generate_verification_token() -> str:
        """Gera um token único para verificação de email."""
        return str(uuid.uuid4())

    @staticmethod
    def send_verification_email(email: str, verification_token: str, username: str = None) -> tuple:
        """
        Envia email de verificação com link.
        
        Args:
            email: Email do utilizador
            verification_token: Token gerado pelo backend
            username: Nome de utilizador (opcional)
        
        Returns:
            (success, message)
        """
        if not verification_token:
            logger.warning("[AVISO] Token de verificação ausente para envio de email.")
            return False, "Token de verificação em falta."

        try:
            display_name = username or email.split('@')[0]
            
            # URL de verificação
            verify_url = f"{API_BASE_URL}/verify-email?token={verification_token}"
            
            # Preparar email
            subject = "Verificar o seu Email - Password Manager"
            
            html_body = f"""
            <html>
                <body style="font-family: Arial, sans-serif; background-color: #f5f5f5; padding: 20px;">
                    <div style="max-width: 500px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                        <h2 style="color: #2C2F33; margin-top: 0;">Bem-vindo, {display_name}! 👋</h2>
                        
                        <p style="color: #666; font-size: 14px;">
                            Obrigado por se registar no <strong>Password Manager</strong>.
                        </p>
                        
                        <p style="color: #666; font-size: 14px;">
                            Para completar o seu registo, clique no botão abaixo para verificar o seu email:
                        </p>
                        
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="{verify_url}" style="background-color: #22c55e; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">
                                ✅ Verificar Email
                            </a>
                        </div>
                        
                        <p style="color: #999; font-size: 12px; border-top: 1px solid #eee; padding-top: 20px;">
                            Ou copie este link:<br/>
                            <code style="background-color: #f5f5f5; padding: 8px; border-radius: 3px; word-break: break-all;">
                                {verify_url}
                            </code>
                        </p>
                        
                        <p style="color: #999; font-size: 12px;">
                            Este link expira em 24 horas.
                        </p>
                    </div>
                </body>
            </html>
            """
            
            text_body = f"""
            Bem-vindo, {display_name}!
            
            Para verificar o seu email, aceda a este link:
            {verify_url}
            
            Este link expira em 24 horas.
            """
            msg = EmailVerification._build_email_message(email, subject, text_body, html_body)
            success, message = EmailVerification._send_email_message(email, msg)
            if success:
                return True, "Email de verificação enviado!"
            return False, message
        
        except Exception as e:
            logger.error(f"[ERRO] Falha ao enviar email: {str(e)}")
            return False, f"Erro ao enviar email: {str(e)}"

    @staticmethod
    def send_confirmation_email(email: str, username: str = None) -> tuple:
        """Envia email informativo após validação de telemóvel."""
        try:
            display_name = username or email.split("@")[0]
            subject = "Telemóvel confirmado - Password Manager"
            html_body = f"""
            <html>
                <body style="font-family: Arial, sans-serif; background-color: #f5f5f5; padding: 20px;">
                    <div style="max-width: 500px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                        <h2 style="color: #2C2F33; margin-top: 0;">Olá, {display_name}! ✅</h2>
                        <p style="color: #666; font-size: 14px;">
                            O seu telemóvel foi confirmado com sucesso no <strong>Password Manager</strong>.
                        </p>
                        <p style="color: #666; font-size: 14px;">
                            Já pode iniciar sessão e continuar a configurar a sua conta com segurança.
                        </p>
                    </div>
                </body>
            </html>
            """
            text_body = f"""
            Olá, {display_name}!

            O seu telemóvel foi confirmado com sucesso no Password Manager.
            Já pode iniciar sessão e continuar a configurar a sua conta com segurança.
            """
            msg = EmailVerification._build_email_message(email, subject, text_body, html_body)
            success, message = EmailVerification._send_email_message(email, msg)
            if success:
                return True, "Email de confirmação enviado!"
            return False, message
        except Exception as e:
            logger.error(f"[ERRO] Falha ao enviar email de confirmação: {str(e)}")
            return False, f"Erro ao enviar email de confirmação: {str(e)}"
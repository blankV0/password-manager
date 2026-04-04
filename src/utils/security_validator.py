"""
Validador de segurança.

Implementa validações REAIS:
- Força de password (comprimento, complexidade, padrões comuns)
- Formato de email
- Formato de username
- Masking de dados sensíveis para logs

REMOVIDO (security theatre — não fornecia proteção real):
- check_sql_injection: blocklist de keywords bypassável e causa falsos positivos.
  A defesa real é usar parameterized queries (o servidor já faz).
- sanitize_input (XSS): Tkinter não é um browser, XSS não se aplica.
- generate_csrf_token: CSRF não se aplica a apps desktop Tkinter.
- generate_audit_hash: SHA256 bruto sem salt não é adequado para auditoria.
"""

import re
import logging

from src.config.settings import (
    PASSWORD_MIN_LENGTH,
    COMMON_PASSWORD_PATTERNS,
    SECURITY_LOG_FILE,
    USERNAME_MIN_LENGTH,
    USERNAME_MAX_LENGTH,
    USERNAME_REGEX,
)
from src.utils.logging_config import configure_logging

# Configurar logging
logger = configure_logging(SECURITY_LOG_FILE, logger_name="security", propagate=False)


class SecurityValidator:
    """Validações de segurança da aplicação."""

    @staticmethod
    def mask_email(email: str) -> str:
        if not email or "@" not in email:
            return "***"
        user, domain = email.split("@", 1)
        if len(user) <= 1:
            masked_user = "*"
        else:
            masked_user = f"{user[0]}***"
        return f"{masked_user}@{domain}"

    @staticmethod
    def mask_phone(phone_number: str) -> str:
        if not phone_number:
            return "****"
        digits = phone_number.replace(" ", "")
        if len(digits) <= 4:
            return "****"
        return f"****{digits[-4:]}"

    @staticmethod
    def validate_password_strength(password: str) -> tuple:
        """
        Valida força da password.

        Requisitos:
        - Mínimo 12 caracteres
        - Pelo menos 1 maiúscula
        - Pelo menos 1 minúscula
        - Pelo menos 1 número
        - Pelo menos 1 caractere especial
        - Não contém padrões comuns

        Returns:
            (valid: bool, errors_or_message: list|str)
        """
        errors = []

        if len(password) < PASSWORD_MIN_LENGTH:
            errors.append(f"Password deve ter pelo menos {PASSWORD_MIN_LENGTH} caracteres")

        if not re.search(r"[A-Z]", password):
            errors.append("Password deve conter pelo menos uma letra maiúscula")

        if not re.search(r"[a-z]", password):
            errors.append("Password deve conter pelo menos uma letra minúscula")

        if not re.search(r"\d", password):
            errors.append("Password deve conter pelo menos um número")

        if not re.search(r"[!@#$%^&*()_+\-=\[\]{};:',.<>?/]", password):
            errors.append("Password deve conter pelo menos um caractere especial")

        for pattern in COMMON_PASSWORD_PATTERNS:
            if pattern.lower() in password.lower():
                errors.append(f"Password contém padrão comum: '{pattern}'")

        if errors:
            logger.warning("[AVISO] Password fraca detectada: %d erro(s)", len(errors))
            return False, errors

        return True, "Password é forte!"

    @staticmethod
    def validate_email(email: str) -> tuple:
        """Valida formato de email."""
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

        if not re.match(pattern, email):
            return False, "Email inválido"

        if len(email) > 254:
            return False, "Email demasiado longo"

        return True, "Email válido"

    @staticmethod
    def validate_username(username: str) -> tuple:
        """
        Valida username para exibição.

        Regras:
        - Comprimento entre USERNAME_MIN_LENGTH e USERNAME_MAX_LENGTH
        - Apenas letras, números, ponto, underscore e hífen
        """
        if not username:
            return False, "Username é obrigatório"

        if len(username) < USERNAME_MIN_LENGTH or len(username) > USERNAME_MAX_LENGTH:
            return False, (
                f"Username deve ter entre {USERNAME_MIN_LENGTH} e {USERNAME_MAX_LENGTH} caracteres"
            )

        if not re.match(USERNAME_REGEX, username):
            return False, "Username contém caracteres inválidos"

        return True, "Username válido"

    @staticmethod
    def validate_registration(email: str, password: str, confirm_password: str, username: str = "") -> tuple:
        """Valida todos os dados de registo."""
        errors = []

        email_valid, email_msg = SecurityValidator.validate_email(email)
        if not email_valid:
            errors.append(email_msg)

        username_valid, username_msg = SecurityValidator.validate_username(username)
        if not username_valid:
            errors.append(username_msg)

        if password != confirm_password:
            errors.append("As passwords não coincidem")

        pwd_valid, pwd_errors = SecurityValidator.validate_password_strength(password)
        if not pwd_valid:
            errors.extend(pwd_errors)

        if errors:
            logger.warning("[AVISO] Validação de registo falhou: %d erro(s)", len(errors))
            return False, errors

        return True, "Todos os dados válidos!"

"""
Sistema de verificação por SMS.
Suporta Twilio para envio de SMS reais ou modo desenvolvimento.
"""

import secrets
import logging
from datetime import datetime, timedelta

from src.config.settings import (
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN,
    TWILIO_PHONE_NUMBER,
    SMS_DEV_MODE,
    SMS_CODE_LENGTH,
    SMS_CODE_EXPIRY_MINUTES,
    SMS_MAX_ATTEMPTS,
    SECURITY_LOG_FILE,
)
from src.utils.security_validator import SecurityValidator
from src.utils.logging_config import configure_logging

# Configurar logging
logger = configure_logging(SECURITY_LOG_FILE, logger_name="security", propagate=False)

try:
    from twilio.rest import Client
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    logger.warning("[AVISO] Twilio não instalado. SMS funciona em modo desenvolvimento.")


class SMSVerification:
    """Gerencia verificação por SMS/telemóvel."""

    _sms_codes = {}
    _twilio_client = None

    @staticmethod
    def _init_twilio() -> bool:
        """Inicializa cliente Twilio se disponível."""
        if not TWILIO_AVAILABLE or not TWILIO_AUTH_TOKEN:
            return False

        try:
            SMSVerification._twilio_client = Client(
                TWILIO_ACCOUNT_SID,
                TWILIO_AUTH_TOKEN,
            )
            logger.info("[OK] Cliente Twilio inicializado")
            return True
        except Exception as e:
            logger.error(f"[ERRO] Falha ao inicializar Twilio: {str(e)}")
            return False

    @staticmethod
    def generate_sms_code(phone_number: str) -> tuple:
        """
        Gera e envia código SMS de 6 dígitos.

        Args:
            phone_number: Número de telemóvel

        Returns:
            (code: str, message: str) - Código gerado e mensagem
        """
        if not SMSVerification.is_valid_phone(phone_number):
            logger.warning(f"[AVISO] Formato de telemóvel inválido: {SecurityValidator.mask_phone(phone_number)}")
            return None, "Número de telemóvel inválido"

        code = str(secrets.randbelow(10**SMS_CODE_LENGTH)).zfill(SMS_CODE_LENGTH)

        SMSVerification._sms_codes[phone_number] = {
            "code": code,
            "created_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(minutes=SMS_CODE_EXPIRY_MINUTES),
            "attempts": 0,
            "verified": False,
        }

        try:
            if TWILIO_AVAILABLE and TWILIO_AUTH_TOKEN:
                SMSVerification._init_twilio()

                if SMSVerification._twilio_client:
                    SMSVerification._twilio_client.messages.create(
                        body=f"Seu código de verificação é: {code}",
                        from_=TWILIO_PHONE_NUMBER,
                        to=phone_number,
                    )
                    logger.info(
                        f"[OK] SMS enviado via Twilio para {SecurityValidator.mask_phone(phone_number)}"
                    )
                    return code, f"Código enviado para ****{phone_number[-4:]}"
        except Exception as e:
            logger.error(f"[ERRO] Falha ao enviar SMS via Twilio: {str(e)}")

        if SMS_DEV_MODE:
            logger.info(
                "[DEV] Código SMS gerado para %s (modo desenvolvimento)",
                SecurityValidator.mask_phone(phone_number),
            )

        return code, f"Código enviado para ****{phone_number[-4:]}"

    @staticmethod
    def verify_sms_code(phone_number: str, code: str) -> tuple:
        """
        Verifica se o código SMS está correto.

        Args:
            phone_number: Número de telemóvel
            code: Código inserido pelo utilizador

        Returns:
            (success: bool, message: str)
        """
        if phone_number not in SMSVerification._sms_codes:
            logger.warning(f"[AVISO] Nenhum código para: {SecurityValidator.mask_phone(phone_number)}")
            return False, "Nenhum código enviado para este telemóvel"

        sms_record = SMSVerification._sms_codes[phone_number]

        if datetime.now() > sms_record["expires_at"]:
            logger.warning(f"[AVISO] Código expirado para: {SecurityValidator.mask_phone(phone_number)}")
            del SMSVerification._sms_codes[phone_number]
            return False, "Código expirado. Solicite um novo código."

        if sms_record["attempts"] >= SMS_MAX_ATTEMPTS:
            logger.critical(
                f"[CRITICO] Máx. tentativas excedidas para: {SecurityValidator.mask_phone(phone_number)}"
            )
            del SMSVerification._sms_codes[phone_number]
            return False, "Muitas tentativas. Código bloqueado."

        sms_record["attempts"] += 1

        if sms_record["code"] != code:
            remaining = SMS_MAX_ATTEMPTS - sms_record["attempts"]
            logger.warning(
                f"[AVISO] Código SMS incorreto para {SecurityValidator.mask_phone(phone_number)} "
                f"({sms_record['attempts']}/{SMS_MAX_ATTEMPTS})"
            )
            return False, f"Código incorreto. {remaining} tentativa(s) restante(s)"

        sms_record["verified"] = True
        sms_record["verified_at"] = datetime.now()

        logger.info(f"[OK] Telemóvel verificado: {SecurityValidator.mask_phone(phone_number)}")

        return True, "Telemóvel confirmado com sucesso!"

    @staticmethod
    def is_valid_phone(phone_number: str) -> bool:
        """
        Valida formato de telemóvel (Portugal).

        Aceita:
        - +351912345678
        - 912345678
        - +351 912345678

        Args:
            phone_number: Número de telemóvel

        Returns:
            bool: True se válido, False caso contrário
        """
        phone = phone_number.replace(" ", "")

        if phone.startswith("+351"):
            return len(phone) == 13 and phone[4:].isdigit()

        if phone.startswith("9"):
            return len(phone) == 9 and phone.isdigit()

        if phone.startswith("+"):
            return len(phone) >= 10 and phone[1:].replace(" ", "").isdigit()

        return False

    @staticmethod
    def format_phone_display(phone_number: str) -> str:
        """
        Formata telemóvel para exibição (mostra apenas últimos 4 dígitos).

        Args:
            phone_number: Número de telemóvel

        Returns:
            str: Telefone formatado para exibição (ex: ****5678)
        """
        phone = phone_number.replace(" ", "")
        return f"****{phone[-4:]}"

    @staticmethod
    def resend_sms_code(phone_number: str) -> tuple:
        """
        Resgera e envia novo código SMS.

        Args:
            phone_number: Número de telemóvel

        Returns:
            (success: bool, message: str)
        """
        if phone_number in SMSVerification._sms_codes:
            del SMSVerification._sms_codes[phone_number]

        code, message = SMSVerification.generate_sms_code(phone_number)

        if code:
            logger.info(f"[OK] Novo código SMS reenviado para: {SecurityValidator.mask_phone(phone_number)}")
            return True, message

        return False, message

    @staticmethod
    def cleanup_expired_codes() -> int:
        """
        Remove códigos SMS expirados.

        Returns:
            int: Número de códigos removidos
        """
        removed = 0
        phones_to_remove = []

        for phone, record in SMSVerification._sms_codes.items():
            if datetime.now() > record["expires_at"]:
                phones_to_remove.append(phone)

        for phone in phones_to_remove:
            del SMSVerification._sms_codes[phone]
            removed += 1

        if removed > 0:
            logger.info(f"[INFO] {removed} código(s) SMS expirado(s) removido(s)")

        return removed

"""
Configurações centralizadas da aplicação.

Fonte ÚNICA de configuração: variáveis de ambiente (.env / env vars).
Segue o princípio 12-factor: configuração separada do código.

NUNCA guardar segredos neste ficheiro — usar .env (que está no .gitignore).
"""

import os
from pathlib import Path

# ── Diretório raiz da aplicação ──────────────────────────────────────────────
APP_ROOT = Path(__file__).resolve().parent.parent.parent


def _load_dotenv(dotenv_path: Path) -> None:
    """Carrega variáveis do ficheiro .env para os.environ (se existir).

    Não sobrescreve variáveis já definidas no ambiente — env vars
    do sistema têm sempre prioridade sobre o ficheiro .env.
    """
    if not dotenv_path.exists():
        return
    try:
        for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("\"").strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except Exception:
        pass


_load_dotenv(APP_ROOT / ".env")

# ═════════════════════════════════════════════════════════════════════════════
# API (Self-hosted Auth Server)
# ═════════════════════════════════════════════════════════════════════════════
API_BASE_URL = os.getenv("API_BASE_URL", "https://localhost:8000").rstrip("/")
API_TIMEOUT = int(os.getenv("API_TIMEOUT", "10"))
API_RETRY_TOTAL = int(os.getenv("API_RETRY_TOTAL", "3"))
API_RETRY_BACKOFF = float(os.getenv("API_RETRY_BACKOFF", "0.5"))
API_KEY = os.getenv("API_KEY", "")
API_KEY_REQUIRED = os.getenv("API_KEY_REQUIRED", "0") == "1"

# ═════════════════════════════════════════════════════════════════════════════
# Logging
# ═════════════════════════════════════════════════════════════════════════════
LOG_DIR = APP_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

APP_LOG_FILE = LOG_DIR / "app.log"
SECURITY_LOG_FILE = LOG_DIR / "security.log"
REGISTRATION_LOG_FILE = LOG_DIR / "registration.log"

# ═════════════════════════════════════════════════════════════════════════════
# Email (opcional)
# ═════════════════════════════════════════════════════════════════════════════
EMAIL_SENDER = os.getenv("EMAIL_SENDER", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
EMAIL_SMTP_SERVER = os.getenv("EMAIL_SMTP_SERVER", "smtp.gmail.com")
EMAIL_SMTP_PORT = int(os.getenv("EMAIL_SMTP_PORT", "465"))
EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "0") == "1"

# ═════════════════════════════════════════════════════════════════════════════
# SMS (Twilio — opcional)
# ═════════════════════════════════════════════════════════════════════════════
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")
SMS_DEV_MODE = os.getenv("SMS_DEV_MODE", "1") == "1"
SMS_ENABLED = os.getenv("SMS_ENABLED", "0") == "1"

# ═════════════════════════════════════════════════════════════════════════════
# Email Verification
# ═════════════════════════════════════════════════════════════════════════════
EMAIL_VERIFICATION_BASE_URL = os.getenv("EMAIL_VERIFICATION_BASE_URL", "http://localhost:8000")

# ═════════════════════════════════════════════════════════════════════════════
# UI (Tkinter)
# ═════════════════════════════════════════════════════════════════════════════
WINDOW_TITLE = "Password Manager - Login"
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800
WINDOW_RESIZABLE = False

# ═════════════════════════════════════════════════════════════════════════════
# Segurança
# ═════════════════════════════════════════════════════════════════════════════
PASSWORD_MIN_LENGTH = 12
SMS_CODE_LENGTH = 6
SMS_CODE_EXPIRY_MINUTES = 10
SMS_MAX_ATTEMPTS = 3
EMAIL_TOKEN_EXPIRY_HOURS = 24

# Autenticação / Rate limiting
LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 300
LOGIN_COOLDOWN_SECONDS = 300

# Username
USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 30
USERNAME_REGEX = r"^[a-zA-Z0-9._-]+$"

# Padrões comuns a evitar em passwords
COMMON_PASSWORD_PATTERNS = ["123", "abc", "password", "qwerty", "admin"]

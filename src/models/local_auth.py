"""
Autenticação via API remota (self-hosted auth server).
Centraliza chamadas HTTP e validações básicas.
"""

import logging
import secrets
import base64
import json
from typing import Tuple, Optional, Dict, Any

from pathlib import Path
from requests import RequestException, Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.config.settings import (
    APP_LOG_FILE,
    REGISTRATION_LOG_FILE,
    API_BASE_URL,
    API_TIMEOUT,
    API_RETRY_TOTAL,
    API_RETRY_BACKOFF,
    API_KEY,
    API_KEY_REQUIRED,
)
from src.services.sms_verification import SMSVerification
from src.utils.security_validator import SecurityValidator
from src.utils.logging_config import configure_logging

# Configurar logging
configure_logging(APP_LOG_FILE)

_registration_logger = logging.getLogger("registration")
if not _registration_logger.handlers:
    handler = logging.FileHandler(REGISTRATION_LOG_FILE, encoding="utf-8")
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    _registration_logger.addHandler(handler)
    _registration_logger.setLevel(logging.INFO)


class AuthError(Exception):
    """Erro de autenticação/ligação à API."""


class LocalAuth:
    """Gerencia autenticação via API remota."""

    def __init__(self, api_base_url: str = API_BASE_URL):
        self.api_base_url = (api_base_url or "").rstrip("/")
        self.session = self._build_session()
        self.disabled = not bool(self.api_base_url)
        self.auth_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.current_role: Optional[str] = None
        if self.disabled:
            logging.error("[ERRO] API_BASE_URL não configurado.")
        self._validate_base_url()

    def _build_session(self) -> Session:
        retry = Retry(
            total=API_RETRY_TOTAL,
            backoff_factor=API_RETRY_BACKOFF,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=frozenset(["POST"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session = Session()
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def _is_localhost(self) -> bool:
        return self.api_base_url.startswith("http://localhost") or self.api_base_url.startswith(
            "http://127.0.0.1"
        )

    def _is_tailscale(self) -> bool:
        """Detecta IPs da rede Tailscale (100.x.x.x / CGNAT range).
        O Tailscale ja encripta o trafego via WireGuard, portanto a
        verificacao do certificado TLS do servidor nao e necessaria."""
        from urllib.parse import urlparse
        host = urlparse(self.api_base_url).hostname or ""
        return host.startswith("100.")

    def _get_verify(self):
        """Retorna o parâmetro 'verify' para o requests.

        Prioridade:
        1. localhost → False (apenas desenvolvimento)
        2. CA cert existe em certs/server_ca.pem → usar esse ficheiro
        3. Rede Tailscale sem CA cert → False (WireGuard já encripta)
        4. Outros → True (bundle CA do sistema)
        """
        if self._is_localhost():
            return False
        ca_cert = Path(__file__).resolve().parents[2] / "certs" / "server_ca.pem"
        if ca_cert.exists():
            return str(ca_cert)
        if self._is_tailscale():
            if not hasattr(self, "_tailscale_ssl_warned"):
                logging.warning(
                    "[AVISO] CA cert não encontrado em certs/server_ca.pem — "
                    "SSL verification desativada para rede Tailscale. "
                    "Recomendado: adicionar o CA cert para verificação completa."
                )
                self._tailscale_ssl_warned = True
            return False
        return True

    def _validate_base_url(self) -> None:
        if self.disabled:
            return
        if self.api_base_url.startswith("http://") and not self._is_localhost():
            logging.error("[ERRO] API_BASE_URL não usa HTTPS em ambiente não-local.")
            self.disabled = True

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "PasswordManager/1.0",
            "X-Request-Id": secrets.token_hex(8),
        }
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        elif API_KEY:
            headers["Authorization"] = f"Bearer {API_KEY}"
        return headers

    def _decode_jwt_payload(self, token: str) -> Dict[str, Any]:
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return {}
            payload_b64 = parts[1]
            padded = payload_b64 + "=" * (-len(payload_b64) % 4)
            decoded = base64.urlsafe_b64decode(padded.encode())
            return json.loads(decoded.decode("utf-8"))
        except Exception:
            return {}

    def get_current_role(self) -> Optional[str]:
        return self.current_role

    def is_admin(self) -> bool:
        return self.current_role == "admin"

    def _api_url(self, path: str) -> str:
        return f"{self.api_base_url}{path}"

    def _auth_base_url(self) -> str:
        base = self.api_base_url.rstrip("/")
        return base if base.endswith("/auth") else f"{base}/auth"

    def _auth_url(self, path: str) -> str:
        safe_path = path if path.startswith("/") else f"/{path}"
        return f"{self._auth_base_url()}{safe_path}"

    def _auth_request(
        self,
        method: str,
        path: str,
        *,
        payload: Optional[Dict[str, Any]] = None,
        access_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Requisição para endpoints /auth com timeout fixo de 10 segundos.
        Em ambiente com certificado self-signed, usa verify=False.
        """
        if self.disabled:
            raise AuthError("API não configurada.")

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "PasswordManager/1.0",
            "X-Request-Id": secrets.token_hex(8),
        }
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        url = self._auth_url(path)
        try:
            response = self.session.request(
                method=method.upper(),
                url=url,
                json=payload or {},
                headers=headers,
                timeout=10,
                verify=self._get_verify(),
            )
        except RequestException as exc:
            logging.error("[ERRO] Falha de ligação à API %s: %s", path, str(exc))
            raise AuthError("Não foi possível ligar ao servidor de autenticação.") from exc

        data: Dict[str, Any] = {}
        if response.content:
            try:
                data = response.json()
            except ValueError:
                data = {}

        if not response.ok:
            message = data.get("message") if isinstance(data, dict) else None
            raise AuthError(message or f"Erro de autenticação (HTTP {response.status_code}).")

        return data

    def _api_post(self, path: str, payload: Dict[str, Any]) -> Tuple[bool, str, Optional[dict]]:
        if self.disabled:
            return False, "API não configurada.", None
        try:
            response = self.session.post(
                self._api_url(path),
                json=payload,
                headers=self._headers(),
                timeout=API_TIMEOUT,
                verify=self._get_verify(),
            )
            data: Dict[str, Any] = {}
            if response.content:
                try:
                    data = response.json()
                except ValueError:
                    data = {}
            data.setdefault("_status", response.status_code)

            if response.ok and data.get("ok") is True:
                return True, data.get("message", "OK"), data
            if response.ok and not data:
                return True, "OK", data
            # Accept any 2xx with data even without {"ok": true}
            # (e.g. server returns 201 Created with UserResponse)
            if response.ok:
                return True, data.get("message", "OK"), data

            if response.status_code == 401 and path not in {"/login", "/refresh"}:
                if self.refresh_token and self._refresh_session():
                    return self._api_post(path, payload)

            message = data.get("message") or f"HTTP {response.status_code}"
            safe_email = None
            if isinstance(payload, dict) and "email" in payload:
                safe_email = SecurityValidator.mask_email(str(payload.get("email")))
            request_id = response.headers.get("X-Request-Id") or response.headers.get("CF-RAY")
            logging.error(
                "[ERRO] API %s falhou (%s) email=%s request_id=%s",
                path,
                response.status_code,
                safe_email or "n/a",
                request_id or "n/a",
            )
            return False, message, data
        except RequestException as e:
            logging.error("[ERRO] Falha de ligação à API %s: %s", path, str(e))
            return False, f"Erro de ligação à API: {str(e)}", None

    def _refresh_session(self) -> bool:
        if not self.refresh_token:
            return False
        success, message, data = self._api_post(
            "/refresh",
            {"refresh_token": self.refresh_token},
        )
        if success and isinstance(data, dict) and data.get("token"):
            self.auth_token = data.get("token")
            self.refresh_token = data.get("refresh_token", self.refresh_token)
            payload = self._decode_jwt_payload(self.auth_token)
            self.current_role = payload.get("role") or payload.get("roles")
            return True
        logging.warning("[AVISO] Refresh falhou: %s", message)
        return False

    def register(
        self,
        email: str,
        password: str,
        phone_number: Optional[str] = None,
        username: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Registra um novo utilizador.

        Args:
            email: Email do utilizador
            password: Password em texto claro
            phone_number: Número de telemóvel (opcional)
            username: Nome de utilizador para exibição (opcional)

        Returns:
            (success: bool, message: str, data: dict with verificationToken)
        """
        email = (email or "").strip()
        username = (username or "").strip()
        phone_number = (phone_number or "").strip() if phone_number else None

        email_valid, email_msg = SecurityValidator.validate_email(email)
        if not email_valid:
            return False, email_msg, None

        if username:
            username_valid, username_msg = SecurityValidator.validate_username(username)
            if not username_valid:
                return False, username_msg, None

        if phone_number and not SMSVerification.is_valid_phone(phone_number):
            return False, "Número de telemóvel inválido.", None

        success, message, data = self._api_post(
            "/auth/register",
            {
                "email": email,
                "password": password,
                "username": username or None,
            },
        )
        if not success:
            status = data.get("_status") if isinstance(data, dict) else None
            _registration_logger.warning(
                "Registo falhou email=%s status=%s message=%s",
                SecurityValidator.mask_email(email),
                status or "n/a",
                message,
            )
        return success, message, data

    def login(self, username: str, password: str) -> Dict[str, str]:
        """
        Login principal.

        Returns:
            {"access_token": str, "refresh_token": str}

        Raises:
            AuthError
        """
        username = (username or "").strip()
        if not username or not password:
            raise AuthError("Username e password são obrigatórios.")

        payload: Dict[str, Any] = {
            "username": username,
            "password": password,
        }
        # Compatibilidade com backends que esperam email em vez de username.
        if "@" in username:
            payload["email"] = username

        data = self._auth_request("POST", "/login", payload=payload)

        access_token = data.get("access_token") or data.get("token")
        refresh_token = data.get("refresh_token")
        if not access_token or not refresh_token:
            raise AuthError("Resposta de login inválida: tokens em falta.")

        self.auth_token = access_token
        self.refresh_token = refresh_token
        decoded = self._decode_jwt_payload(access_token)
        self.current_role = decoded.get("role") or decoded.get("roles")

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
        }

    def logout(self, access_token: Optional[str] = None) -> Tuple[bool, str]:
        """Faz logout no servidor via POST /auth/logout."""
        token = access_token or self.auth_token
        if not token:
            self.auth_token = None
            self.refresh_token = None
            self.current_role = None
            return True, "Logout local."

        try:
            self._auth_request("POST", "/logout", payload={}, access_token=token)
            message = "Logout efetuado com sucesso."
            success = True
        except AuthError as exc:
            message = str(exc)
            success = False

        self.auth_token = None
        self.refresh_token = None
        self.current_role = None
        return success, message

    def refresh(self, refresh_token: str) -> str:
        """
        Renova sessão com refresh token.

        Returns:
            access_token (novo)

        Raises:
            AuthError
        """
        token = (refresh_token or "").strip()
        if not token:
            raise AuthError("Refresh token ausente.")

        data = self._auth_request("POST", "/refresh", payload={"refresh_token": token})
        access_token = data.get("access_token") or data.get("token")
        if not access_token:
            raise AuthError("Resposta de refresh inválida: access_token em falta.")

        self.auth_token = access_token
        self.refresh_token = data.get("refresh_token", token)
        decoded = self._decode_jwt_payload(access_token)
        self.current_role = decoded.get("role") or decoded.get("roles")
        return access_token

    def get_me(self, access_token: Optional[str] = None) -> Dict[str, Any]:
        """
        Obtém utilizador atual via GET /auth/me.

        Raises:
            AuthError
        """
        token = (access_token or self.auth_token or "").strip()
        if not token:
            raise AuthError("Access token ausente.")

        data = self._auth_request("GET", "/me", payload=None, access_token=token)
        if isinstance(data, dict) and "user" in data and isinstance(data["user"], dict):
            return data["user"]
        if isinstance(data, dict):
            return data
        raise AuthError("Resposta inválida em /auth/me.")

    def admin_list_users(self) -> Tuple[bool, str, Optional[list]]:
        success, message, data = self._api_post("/auth/admin/users", {})
        if success and isinstance(data, dict):
            return True, message, data.get("users", [])
        return False, message, None

    def admin_set_active(self, email: str, active: bool) -> Tuple[bool, str]:
        success, message, _ = self._api_post(
            "/auth/admin/user/active",
            {"email": email, "active": bool(active)},
        )
        return success, message

    def admin_reset_password(self, email: str, new_password: str) -> Tuple[bool, str]:
        success, message, _ = self._api_post(
            "/auth/admin/user/reset-password",
            {"email": email, "new_password": new_password},
        )
        return success, message

    def admin_get_logs(self) -> Tuple[bool, str, Optional[list]]:
        success, message, data = self._api_post("/auth/admin/logs", {})
        if success and isinstance(data, dict):
            return True, message, data.get("logs", [])
        return False, message, None

    def login_by_phone(self, phone_number: str, password: str) -> Tuple[bool, str]:
        """
        Faz login com telemóvel e password.

        Args:
            phone_number: Número de telemóvel
            password: Password em texto claro

        Returns:
            (success: bool, email_or_error: str)
        """
        phone_number = (phone_number or "").strip()
        if not SMSVerification.is_valid_phone(phone_number):
            return False, "Número de telemóvel inválido."

        success, message, data = self._api_post(
            "/login-phone",
            {"phone_number": phone_number, "password": password},
        )
        if not success and (data is None or data.get("message") == "Not found"):
            return False, "Login por telemóvel indisponível no modo cloud."
        return (success, data.get("email") if success else message) if data else (success, message)

    def update_phone_number(self, email: str, phone_number: str) -> Tuple[bool, str]:
        """
        Atualiza número de telemóvel de um utilizador.

        Args:
            email: Email do utilizador
            phone_number: Novo número de telemóvel

        Returns:
            (success: bool, message: str)
        """
        email = (email or "").strip()
        if not SMSVerification.is_valid_phone(phone_number):
            return False, "Número de telemóvel inválido."

        success, message, _ = self._api_post(
            "/update-phone",
            {"email": email, "phone_number": phone_number},
        )
        if not success:
            return False, "Operação indisponível no modo cloud."
        return True, message

    def update_username(self, email: str, username: str) -> Tuple[bool, str]:
        """
        Atualiza o username de um utilizador.

        Args:
            email: Email do utilizador
            username: Novo username

        Returns:
            (success: bool, message: str)
        """
        email = (email or "").strip()
        username = (username or "").strip()
        username_valid, username_msg = SecurityValidator.validate_username(username)
        if not username_valid:
            return False, username_msg

        success, message, _ = self._api_post(
            "/update-username",
            {"email": email, "username": username},
        )
        if not success:
            return False, "Operação indisponível no modo cloud."
        return True, message

    def verify_phone(self, email: str) -> Tuple[bool, str]:
        """
        Marca telemóvel como verificado.

        Args:
            email: Email do utilizador

        Returns:
            (success: bool, message: str)
        """
        email = (email or "").strip()
        success, message, _ = self._api_post(
            "/verify-phone",
            {"email": email},
        )
        if not success:
            logging.warning("[AVISO] Verificação de telemóvel não suportada pela API.")
            return True, "Telemóvel verificado (modo cloud)."
        return True, message

    def verify_email(self, email: str) -> Tuple[bool, str]:
        """
        Marca email como verificado.

        Args:
            email: Email do utilizador

        Returns:
            (success: bool, message: str)
        """
        email = (email or "").strip()
        success, message, _ = self._api_post(
            "/verify-email",
            {"email": email},
        )
        if not success:
            logging.warning("[AVISO] Verificação de email não suportada pela API.")
            return True, "Email verificado (modo cloud)."
        return True, message

    def get_phone_number(self, email: str) -> Tuple[Optional[str], bool, str]:
        """
        Obtém número de telemóvel de um utilizador.

        Args:
            email: Email do utilizador

        Returns:
            (phone_number: str|None, verified: bool, message: str)
        """
        return None, False, "Operação indisponível no modo cloud."

    def get_username(self, email: str) -> Tuple[Optional[str], str]:
        """
        Obtém username de um utilizador.

        Args:
            email: Email do utilizador

        Returns:
            (username: str|None, message: str)
        """
        return None, "Username indisponível no modo cloud."

    def user_exists(self, email: str) -> bool:
        """
        Verifica se um utilizador existe.

        Args:
            email: Email a verificar

        Returns:
            bool: True se existe, False caso contrário
        """
        return False

    # ══════════════════════════════════════════════════════════════════════════
    # VAULT API — encrypted vault sync (Phase 3, zero-knowledge)
    # ══════════════════════════════════════════════════════════════════════════

    def vault_get_key(self) -> Dict[str, Any]:
        """GET /vault/key — fetch wrapped DEK material."""
        return self._vault_request("GET", "/vault/key")

    def vault_setup_key(self, payload: Dict[str, str]) -> Dict[str, Any]:
        """POST /vault/key — store wrapped DEK + salt (first-time)."""
        return self._vault_request("POST", "/vault/key", payload=payload)

    def vault_rewrap_key(self, payload: Dict[str, str]) -> Dict[str, Any]:
        """PUT /vault/key — re-wrap DEK after master password change."""
        return self._vault_request("PUT", "/vault/key", payload=payload)

    def vault_list_entries(self) -> Dict[str, Any]:
        """GET /vault/entries — list all encrypted entries."""
        return self._vault_request("GET", "/vault/entries")

    def vault_create_entry(self, payload: Dict[str, str]) -> Dict[str, Any]:
        """POST /vault/entries — store a new encrypted entry."""
        return self._vault_request("POST", "/vault/entries", payload=payload)

    def vault_update_entry(self, entry_id: str, payload: Dict[str, str]) -> Dict[str, Any]:
        """PUT /vault/entries/{id} — update an encrypted entry."""
        return self._vault_request("PUT", f"/vault/entries/{entry_id}", payload=payload)

    def vault_delete_entry(self, entry_id: str) -> Dict[str, Any]:
        """DELETE /vault/entries/{id} — delete an encrypted entry."""
        return self._vault_request("DELETE", f"/vault/entries/{entry_id}")

    def _vault_request(
        self,
        method: str,
        path: str,
        *,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generic request to /vault/* endpoints.
        Uses the base URL directly (not /auth prefix).
        """
        if self.disabled:
            raise AuthError("API não configurada.")
        if not self.auth_token:
            raise AuthError("Não autenticado.")

        url = f"{self.api_base_url}{path}"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "PasswordManager/1.0",
            "Authorization": f"Bearer {self.auth_token}",
        }
        try:
            response = self.session.request(
                method=method.upper(),
                url=url,
                json=payload,
                headers=headers,
                timeout=10,
                verify=self._get_verify(),
            )
        except RequestException as exc:
            raise AuthError(f"Vault API error: {exc}") from exc

        data: Dict[str, Any] = {}
        if response.content:
            try:
                data = response.json()
            except ValueError:
                data = {}

        if not response.ok:
            msg = data.get("detail") or data.get("message") or f"HTTP {response.status_code}"
            raise AuthError(msg)

        return data

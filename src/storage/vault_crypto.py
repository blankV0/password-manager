"""
src.storage.vault_crypto — Client-side vault encryption/decryption.

Zero-knowledge architecture:
    Master Password → Argon2id → KEK (32 bytes)
                                   │
    DEK (random 256-bit) ← wrapped with KEK → stored on server
         │
         └─► AES-256-GCM encrypt/decrypt each vault entry

The server NEVER receives the master password, KEK, or DEK.
It only stores opaque ciphertext (wrapped DEK + encrypted entries).
"""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass
from typing import Any, Optional

from src.core.crypto import CryptoProvider, DecryptionError
from src.core.secure_memory import SecureBytes, secure_zero

logger = logging.getLogger(__name__)

__all__ = [
    "VaultCrypto",
    "VaultCryptoError",
    "DecryptedEntry",
]


class VaultCryptoError(Exception):
    """Raised on encryption/decryption failures (wrong password, corrupt data)."""


@dataclass
class DecryptedEntry:
    """A decrypted vault entry (lives in memory briefly)."""
    id: str
    site: str
    username: str
    password: str
    notes: str
    created_at: int = 0
    updated_at: int = 0


class VaultCrypto:
    """
    Manages KEK/DEK lifecycle and entry encryption for the vault.

    Usage::

        vc = VaultCrypto()

        # First-time setup
        salt, wrapped = vc.setup_new_vault("MyMasterPassword!")
        # → send wrapped to server via API

        # Returning user — unlock vault
        vc.unlock("MyMasterPassword!", salt_b64, wrapped_dek_b64, nonce_b64, tag_b64)

        # Encrypt entry before sending to server
        ct_b64, nonce_b64, tag_b64 = vc.encrypt_entry({...})

        # Decrypt entry received from server
        entry_dict = vc.decrypt_entry(ct_b64, nonce_b64, tag_b64)

        # Lock vault — wipe keys from memory
        vc.lock()
    """

    def __init__(self) -> None:
        self._crypto = CryptoProvider()
        self._dek: Optional[bytearray] = None
        self._kek: Optional[bytearray] = None

    @property
    def is_unlocked(self) -> bool:
        return self._dek is not None

    # ── First-time vault setup ───────────────────────────────────────────

    def setup_new_vault(self, master_password: str) -> dict[str, str]:
        """
        Create a brand-new vault: generate salt, derive KEK, generate DEK,
        wrap DEK with KEK.

        Returns a dict with base64-encoded material to send to the server::

            {
                "kek_salt_b64": "...",
                "wrapped_dek_b64": "...",
                "dek_nonce_b64": "...",
                "dek_tag_b64": "...",
            }

        After calling this, the vault is unlocked (DEK in memory).
        """
        self.lock()  # wipe any previous keys

        salt = self._crypto.generate_salt()
        kek = self._crypto.derive_kek(master_password, salt)
        dek = self._crypto.generate_dek()
        wrapped_dek, nonce, tag = self._crypto.wrap_dek(dek, kek)

        self._kek = kek
        self._dek = dek

        logger.info("[VAULT] New vault created (DEK generated, wrapped with KEK)")

        return {
            "kek_salt_b64": base64.b64encode(salt).decode(),
            "wrapped_dek_b64": base64.b64encode(wrapped_dek).decode(),
            "dek_nonce_b64": base64.b64encode(nonce).decode(),
            "dek_tag_b64": base64.b64encode(tag).decode(),
        }

    # ── Unlock existing vault ────────────────────────────────────────────

    def unlock(
        self,
        master_password: str,
        kek_salt_b64: str,
        wrapped_dek_b64: str,
        dek_nonce_b64: str,
        dek_tag_b64: str,
    ) -> None:
        """
        Unlock an existing vault by deriving KEK and unwrapping DEK.

        Raises:
            VaultCryptoError: if the master password is wrong or data corrupt.
        """
        self.lock()  # wipe any previous keys

        try:
            salt = base64.b64decode(kek_salt_b64)
            wrapped_dek = base64.b64decode(wrapped_dek_b64)
            nonce = base64.b64decode(dek_nonce_b64)
            tag = base64.b64decode(dek_tag_b64)
        except Exception as exc:
            raise VaultCryptoError("Invalid base64 vault key data.") from exc

        kek = self._crypto.derive_kek(master_password, salt)
        try:
            dek = self._crypto.unwrap_dek(wrapped_dek, kek, nonce, tag)
        except DecryptionError as exc:
            secure_zero(kek)
            raise VaultCryptoError(
                "Não foi possível desbloquear o vault — password incorreta ou dados corrompidos."
            ) from exc

        self._kek = kek
        self._dek = dek
        logger.info("[VAULT] Vault unlocked successfully")

    # ── Lock vault (wipe keys from memory) ───────────────────────────────

    def lock(self) -> None:
        """Securely wipe KEK and DEK from memory."""
        if self._kek is not None:
            secure_zero(self._kek)
            self._kek = None
        if self._dek is not None:
            secure_zero(self._dek)
            self._dek = None

    def __del__(self) -> None:
        self.lock()

    # ── Encrypt / Decrypt entries ────────────────────────────────────────

    def encrypt_entry(self, entry_data: dict[str, Any]) -> tuple[str, str, str]:
        """
        Encrypt a vault entry dict to base64-encoded (ciphertext, nonce, tag).

        The entry_data should contain: site, username, password, notes.

        Returns:
            (encrypted_data_b64, nonce_b64, tag_b64)

        Raises:
            VaultCryptoError: if vault is locked.
        """
        if self._dek is None:
            raise VaultCryptoError("Vault is locked — unlock first.")

        plaintext = json.dumps(entry_data, ensure_ascii=False).encode("utf-8")
        ct, nonce, tag = self._crypto.encrypt_entry(plaintext, self._dek)

        return (
            base64.b64encode(ct).decode(),
            base64.b64encode(nonce).decode(),
            base64.b64encode(tag).decode(),
        )

    def decrypt_entry(
        self,
        encrypted_data_b64: str,
        nonce_b64: str,
        tag_b64: str,
    ) -> dict[str, Any]:
        """
        Decrypt a vault entry from base64-encoded server data.

        Returns:
            dict with keys: site, username, password, notes

        Raises:
            VaultCryptoError: if vault is locked or data is corrupt.
        """
        if self._dek is None:
            raise VaultCryptoError("Vault is locked — unlock first.")

        try:
            ct = base64.b64decode(encrypted_data_b64)
            nonce = base64.b64decode(nonce_b64)
            tag = base64.b64decode(tag_b64)
        except Exception as exc:
            raise VaultCryptoError("Invalid base64 entry data.") from exc

        try:
            plaintext = self._crypto.decrypt_entry(ct, self._dek, nonce, tag)
        except DecryptionError as exc:
            raise VaultCryptoError("Entry decryption failed — data corrupt.") from exc

        try:
            return json.loads(plaintext.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise VaultCryptoError("Decrypted data is not valid JSON.") from exc

    # ── Re-wrap DEK (master password change) ─────────────────────────────

    def rewrap_dek(self, new_master_password: str) -> dict[str, str]:
        """
        Re-wrap the DEK with a new master password.

        The vault must be unlocked (DEK in memory).

        Returns the same dict format as setup_new_vault().
        """
        if self._dek is None:
            raise VaultCryptoError("Vault is locked — unlock first.")

        new_salt = self._crypto.generate_salt()
        new_kek = self._crypto.derive_kek(new_master_password, new_salt)
        wrapped_dek, nonce, tag = self._crypto.wrap_dek(self._dek, new_kek)

        # Replace old KEK with new one
        if self._kek is not None:
            secure_zero(self._kek)
        self._kek = new_kek

        logger.info("[VAULT] DEK re-wrapped with new master password")

        return {
            "kek_salt_b64": base64.b64encode(new_salt).decode(),
            "wrapped_dek_b64": base64.b64encode(wrapped_dek).decode(),
            "dek_nonce_b64": base64.b64encode(nonce).decode(),
            "dek_tag_b64": base64.b64encode(tag).decode(),
        }

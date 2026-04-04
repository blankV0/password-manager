"""
src.core.crypto — Fachada criptográfica de alto nível.

Este módulo é o ÚNICO ponto de entrada que as camadas superiores
(services/, storage/) devem importar. Encapsula:
    • Derivação de chaves  (Argon2id)
    • Encriptação          (AES-256-GCM)
    • Geração segura de aleatoriedade
    • Limpeza segura de memória

A GUI / UI NUNCA deve importar este módulo directamente.
Apenas services/ e storage/ devem usar src.core.

Arquitectura KEK/DEK (Key-Encryption-Key / Data-Encryption-Key):
    ┌─────────────────────────────────────────────────────┐
    │  Master Password  ──► Argon2id ──► KEK (32 bytes)   │
    │                                       │              │
    │  DEK (gerado aleatório) ◄─── encriptado com KEK     │
    │       │                                              │
    │       └──► encripta/desencripta cada entrada vault   │
    └─────────────────────────────────────────────────────┘

    Benefícios:
    • Mudar master password = re-encriptar só o DEK (rápido)
    • DEK nunca é derivado — tem entropia máxima (256 bits)
    • KEK vive em memória o mínimo possível

Uso:
    from src.core.crypto import CryptoProvider

    crypto = CryptoProvider()

    # Criar vault novo
    salt = crypto.generate_salt()
    kek  = crypto.derive_kek("MasterPassword123!", salt)
    dek  = crypto.generate_dek()
    wrapped_dek, nonce, tag = crypto.wrap_dek(dek, kek)

    # Encriptar entrada
    ct, n, t = crypto.encrypt_entry(b'{"site":"github.com",...}', dek)

    # Desencriptar entrada
    plaintext = crypto.decrypt_entry(ct, dek, n, t)
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from src.core.encryption import (
    AES_KEY_SIZE,
    NONCE_SIZE,
    TAG_SIZE,
    DecryptionError,
    decrypt,
    encrypt,
)
from src.core.key_derivation import (
    KEY_LENGTH,
    SALT_LENGTH,
    derive_key,
    generate_salt,
)
from src.core.secure_memory import SecureBytes, secure_zero

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

__all__ = [
    "CryptoProvider",
    "DecryptionError",
    "SecureBytes",
    "secure_zero",
]


class CryptoProvider:
    """
    API criptográfica unificada para o Password Manager.

    Todas as operações são stateless — nenhuma chave é guardada
    como atributo de instância. Quem chama é responsável por
    manter e limpar chaves com SecureBytes/secure_zero().
    """

    # ── Constantes expostas (para serialização de metadados) ──

    SALT_LENGTH = SALT_LENGTH
    KEY_LENGTH = KEY_LENGTH
    NONCE_SIZE = NONCE_SIZE
    TAG_SIZE = TAG_SIZE

    # ── Key Derivation ────────────────────────────────────────

    @staticmethod
    def generate_salt() -> bytes:
        """Gera salt aleatório para Argon2id (16 bytes)."""
        return generate_salt()

    @staticmethod
    def derive_kek(master_password: str, salt: bytes) -> bytearray:
        """
        Deriva a Key-Encryption-Key (KEK) a partir da master password.

        Returns:
            bytearray de 32 bytes — DEVE ser limpo com secure_zero()
            quando já não for necessário.
        """
        return derive_key(master_password, salt)

    # ── Data Encryption Key ──────────────────────────────────

    @staticmethod
    def generate_dek() -> bytearray:
        """
        Gera uma Data-Encryption-Key (DEK) aleatória de 256 bits.

        A DEK tem entropia máxima (os.urandom) e é usada para
        encriptar/desencriptar entradas individuais do vault.

        Returns:
            bytearray de 32 bytes — DEVE ser limpo com secure_zero().
        """
        return bytearray(os.urandom(AES_KEY_SIZE))

    @staticmethod
    def wrap_dek(
        dek: bytes | bytearray,
        kek: bytes | bytearray,
    ) -> tuple[bytes, bytes, bytes]:
        """
        Encripta a DEK com a KEK (key wrapping).

        Args:
            dek: Data-Encryption-Key (32 bytes).
            kek: Key-Encryption-Key derivada da master password (32 bytes).

        Returns:
            Tuplo (wrapped_dek, nonce, tag).
        """
        return encrypt(bytes(dek), kek)

    @staticmethod
    def unwrap_dek(
        wrapped_dek: bytes,
        kek: bytes | bytearray,
        nonce: bytes,
        tag: bytes,
    ) -> bytearray:
        """
        Desencripta a DEK usando a KEK.

        Returns:
            bytearray de 32 bytes (a DEK original).

        Raises:
            DecryptionError: master password errada ou dados corrompidos.
        """
        raw = decrypt(wrapped_dek, kek, nonce, tag)
        return bytearray(raw)

    # ── Encriptação de entradas ──────────────────────────────

    @staticmethod
    def encrypt_entry(
        plaintext: bytes,
        dek: bytes | bytearray,
        associated_data: bytes | None = None,
    ) -> tuple[bytes, bytes, bytes]:
        """
        Encripta uma entrada do vault com a DEK.

        Args:
            plaintext:       JSON serializado da entrada (bytes).
            dek:             Data-Encryption-Key (32 bytes).
            associated_data: metadados autenticados (ex.: entry_id).

        Returns:
            Tuplo (ciphertext, nonce, tag).
        """
        return encrypt(plaintext, dek, associated_data)

    @staticmethod
    def decrypt_entry(
        ciphertext: bytes,
        dek: bytes | bytearray,
        nonce: bytes,
        tag: bytes,
        associated_data: bytes | None = None,
    ) -> bytes:
        """
        Desencripta uma entrada do vault.

        Returns:
            bytes: JSON original da entrada.

        Raises:
            DecryptionError: DEK errada ou dados corrompidos.
        """
        return decrypt(ciphertext, dek, nonce, tag, associated_data)

    # ── Utilitários ──────────────────────────────────────────

    @staticmethod
    def secure_random(n: int) -> bytes:
        """Gera n bytes criptograficamente seguros."""
        if n <= 0:
            raise ValueError("n deve ser > 0")
        return os.urandom(n)

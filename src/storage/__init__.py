"""
src.storage — Camada de persistência do vault encriptado (Phase 3).

Módulos:
    vault_crypto  — Encriptação/decriptação client-side (KEK/DEK, AES-256-GCM)
"""

from src.storage.vault_crypto import VaultCrypto, VaultCryptoError, DecryptedEntry

__all__ = ["VaultCrypto", "VaultCryptoError", "DecryptedEntry"]

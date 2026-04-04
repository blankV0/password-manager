"""
src.core — Módulos de segurança e criptografia.

API pública:
    from src.core.crypto import CryptoProvider, DecryptionError
    from src.core.secure_memory import SecureBytes, secure_zero
"""

from src.core.crypto import CryptoProvider, DecryptionError
from src.core.secure_memory import SecureBytes, secure_zero

__all__ = [
    "CryptoProvider",
    "DecryptionError",
    "SecureBytes",
    "secure_zero",
]

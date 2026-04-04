"""
src.core.encryption — Encriptação AES-256-GCM autenticada.

Responsabilidade ÚNICA: encriptar e desencriptar blobs de bytes
com AES-256-GCM (Galois/Counter Mode), que fornece:
    • Confidencialidade  (AES-256)
    • Integridade         (GHASH authentication tag)
    • Autenticação        (GCM — authenticated encryption)

Cada chamada a encrypt() gera um nonce aleatório único de 12 bytes
(96 bits — tamanho recomendado pelo NIST SP 800-38D).

Uso:
    from src.core.encryption import encrypt, decrypt

    key = derive_key(password, salt)     # 32 bytes
    ciphertext, nonce, tag = encrypt(b"dados secretos", key)
    plaintext = decrypt(ciphertext, key, nonce, tag)
"""

from __future__ import annotations

import logging
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)

# ─── Constantes ──────────────────────────────────────────────────────────────

AES_KEY_SIZE: int = 32
"""Tamanho da chave AES em bytes (256 bits)."""

NONCE_SIZE: int = 12
"""Tamanho do nonce em bytes (96 bits — NIST recomendado para GCM)."""

TAG_SIZE: int = 16
"""Tamanho da authentication tag em bytes (128 bits — máximo GCM)."""


# ─── API pública ─────────────────────────────────────────────────────────────

def encrypt(
    plaintext: bytes,
    key: bytes | bytearray,
    associated_data: bytes | None = None,
) -> tuple[bytes, bytes, bytes]:
    """
    Encripta dados com AES-256-GCM.

    Args:
        plaintext:       dados a encriptar (pode ser vazio).
        key:             chave de 32 bytes (AES-256).
        associated_data: dados adicionais autenticados mas NÃO encriptados
                         (ex.: metadados do registo). Opcional.

    Returns:
        Tuplo (ciphertext, nonce, tag):
            • ciphertext — dados encriptados (mesmo comprimento que plaintext).
            • nonce      — 12 bytes aleatórios (guardar junto ao ciphertext).
            • tag        — 16 bytes de autenticação (guardar junto ao ciphertext).

    Raises:
        ValueError: se a chave não tiver 32 bytes.
        TypeError:  se plaintext não for bytes.
    """
    _validate_key(key)
    if not isinstance(plaintext, (bytes, bytearray)):
        raise TypeError(
            f"plaintext deve ser bytes, recebeu {type(plaintext).__name__}"
        )

    nonce = os.urandom(NONCE_SIZE)
    aesgcm = AESGCM(bytes(key))

    # AESGCM.encrypt() devolve ciphertext || tag (concatenados)
    ct_with_tag: bytes = aesgcm.encrypt(nonce, bytes(plaintext), associated_data)

    # Separar ciphertext e tag (tag são os últimos TAG_SIZE bytes)
    ciphertext = ct_with_tag[:-TAG_SIZE]
    tag = ct_with_tag[-TAG_SIZE:]

    logger.debug(
        "Encriptação AES-256-GCM: %d bytes → %d bytes (nonce=%d, tag=%d)",
        len(plaintext),
        len(ciphertext),
        len(nonce),
        len(tag),
    )
    return ciphertext, nonce, tag


def decrypt(
    ciphertext: bytes,
    key: bytes | bytearray,
    nonce: bytes,
    tag: bytes,
    associated_data: bytes | None = None,
) -> bytes:
    """
    Desencripta e verifica dados com AES-256-GCM.

    Args:
        ciphertext:      dados encriptados.
        key:             chave de 32 bytes (a mesma usada para encriptar).
        nonce:           nonce de 12 bytes (o mesmo devolvido por encrypt()).
        tag:             authentication tag de 16 bytes.
        associated_data: os mesmos dados adicionais usados em encrypt().

    Returns:
        bytes: dados originais desencriptados.

    Raises:
        ValueError:            se chave/nonce/tag tiverem tamanho incorrecto.
        DecryptionError:       se a tag de autenticação falhar (dados corrompidos
                               ou chave errada).
        cryptography.exceptions.InvalidTag:
                               excepção nativa — re-embalada como DecryptionError.
    """
    _validate_key(key)
    if len(nonce) != NONCE_SIZE:
        raise ValueError(
            f"Nonce deve ter {NONCE_SIZE} bytes, recebeu {len(nonce)}."
        )
    if len(tag) != TAG_SIZE:
        raise ValueError(
            f"Tag deve ter {TAG_SIZE} bytes, recebeu {len(tag)}."
        )

    aesgcm = AESGCM(bytes(key))

    # Reconstruir o formato que AESGCM.decrypt() espera: ciphertext || tag
    ct_with_tag = bytes(ciphertext) + bytes(tag)

    try:
        plaintext: bytes = aesgcm.decrypt(nonce, ct_with_tag, associated_data)
    except Exception as exc:
        # Normalizar qualquer erro de autenticação para DecryptionError
        logger.warning("Falha na desencriptação AES-256-GCM: %s", exc)
        raise DecryptionError(
            "Desencriptação falhou — chave incorrecta ou dados corrompidos."
        ) from exc

    logger.debug(
        "Desencriptação AES-256-GCM: %d bytes recuperados", len(plaintext)
    )
    return plaintext


# ─── Excepções ───────────────────────────────────────────────────────────────

class DecryptionError(Exception):
    """Erro de desencriptação — tag inválida, chave errada ou dados corrompidos."""


# ─── Helpers internos ────────────────────────────────────────────────────────

def _validate_key(key: bytes | bytearray) -> None:
    """Valida que a chave tem exactamente 32 bytes."""
    if not isinstance(key, (bytes, bytearray)):
        raise TypeError(
            f"key deve ser bytes/bytearray, recebeu {type(key).__name__}"
        )
    if len(key) != AES_KEY_SIZE:
        raise ValueError(
            f"Chave AES-256 deve ter {AES_KEY_SIZE} bytes, recebeu {len(key)}."
        )

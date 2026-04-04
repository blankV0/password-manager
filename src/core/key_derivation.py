"""
src.core.key_derivation — Derivação de chaves com Argon2id.

Responsabilidade ÚNICA: transformar uma password humana + salt aleatório
numa chave criptográfica de comprimento fixo, resistente a brute-force
(GPU / ASIC / FPGA).

Parâmetros Argon2id escolhidos:
    time_cost   = 3          (iterações — OWASP mínimo)
    memory_cost = 65 536 KiB (64 MB — OWASP recomendado)
    parallelism = 2          (threads)
    hash_len    = 32 bytes   (256 bits — para AES-256)
    salt_len    = 16 bytes   (128 bits — NIST recomendado)

Uso:
    from src.core.key_derivation import derive_key, generate_salt

    salt = generate_salt()
    key  = derive_key("minha password forte", salt)
    # key é bytearray(32) — apagar com secure_zero() quando terminar
"""

from __future__ import annotations

import logging
import os

from argon2.low_level import Type, hash_secret_raw

from src.core.secure_memory import SecureBytes

logger = logging.getLogger(__name__)

# ─── Constantes (imutáveis — nunca alterar em runtime) ───────────────────────

ARGON2_TIME_COST: int = 3
"""Número de iterações (passes sobre a memória)."""

ARGON2_MEMORY_COST_KIB: int = 65_536
"""Memória em KiB (64 MB)."""

ARGON2_PARALLELISM: int = 2
"""Grau de paralelismo (threads)."""

KEY_LENGTH: int = 32
"""Comprimento da chave derivada em bytes (256 bits para AES-256)."""

SALT_LENGTH: int = 16
"""Comprimento do salt em bytes (128 bits)."""


# ─── API pública ─────────────────────────────────────────────────────────────

def generate_salt() -> bytes:
    """
    Gera um salt criptograficamente seguro.

    Returns:
        bytes: salt aleatório de SALT_LENGTH bytes.
    """
    return os.urandom(SALT_LENGTH)


def derive_key(password: str, salt: bytes) -> bytearray:
    """
    Deriva uma chave AES-256 a partir de uma password e salt usando Argon2id.

    A chave devolvida é um **bytearray mutável** para poder ser limpo
    com secure_zero() quando já não for necessário.

    Args:
        password: password do utilizador (UTF-8).
        salt:     salt aleatório (deve ter SALT_LENGTH bytes).

    Returns:
        bytearray: chave derivada de KEY_LENGTH bytes.

    Raises:
        ValueError: se salt ou password estiverem vazios / tamanho incorrecto.
    """
    # ── Validação ──
    if not password:
        raise ValueError("Password não pode estar vazia.")
    if not salt or len(salt) < SALT_LENGTH:
        raise ValueError(
            f"Salt deve ter pelo menos {SALT_LENGTH} bytes, recebeu {len(salt) if salt else 0}."
        )

    # ── Derivação ──
    # Converter password para bytes; usar SecureBytes para limpar depois
    pw_bytes = bytearray(password.encode("utf-8"))
    try:
        raw: bytes = hash_secret_raw(
            secret=bytes(pw_bytes),
            salt=salt,
            time_cost=ARGON2_TIME_COST,
            memory_cost=ARGON2_MEMORY_COST_KIB,
            parallelism=ARGON2_PARALLELISM,
            hash_len=KEY_LENGTH,
            type=Type.ID,  # Argon2id
        )
        logger.debug(
            "Chave derivada com sucesso (Argon2id t=%d m=%dKiB p=%d)",
            ARGON2_TIME_COST,
            ARGON2_MEMORY_COST_KIB,
            ARGON2_PARALLELISM,
        )
        # Devolver como bytearray mutável
        return bytearray(raw)
    finally:
        # Limpar password em memória
        from src.core.secure_memory import secure_zero

        secure_zero(pw_bytes)

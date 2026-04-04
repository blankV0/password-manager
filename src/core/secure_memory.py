"""
src.core.secure_memory — Limpeza segura de dados sensíveis em memória.

Garante que chaves, passwords e outros segredos são apagados da RAM
assim que deixam de ser necessários, reduzindo a janela de exposição
a memory-dump attacks.

Uso:
    from src.core.secure_memory import secure_zero, SecureBytes

    key = bytearray(os.urandom(32))
    try:
        ...  # usar key
    finally:
        secure_zero(key)

    # Ou com context manager:
    with SecureBytes(os.urandom(32)) as key:
        ...  # usar bytes(key) ou key directamente
    # key já foi zerado automaticamente
"""

from __future__ import annotations

import ctypes
import logging

logger = logging.getLogger(__name__)


# ─── Primitivas ──────────────────────────────────────────────────────────────

def secure_zero(buffer: bytearray | memoryview) -> None:
    """
    Zera um bytearray ou memoryview in-place.

    Usa ctypes.memset para garantir que o compilador / GC não optimiza
    a operação (write-after-free elimination).

    Args:
        buffer: bytearray ou memoryview mutável a limpar.

    Raises:
        TypeError: se buffer não for mutável (ex.: bytes imutável).
    """
    if isinstance(buffer, memoryview):
        if buffer.readonly:
            raise TypeError("Não é possível limpar um memoryview read-only.")
        n = buffer.nbytes
        ctypes.memset(ctypes.addressof(ctypes.c_char.from_buffer(buffer)), 0, n)
    elif isinstance(buffer, bytearray):
        n = len(buffer)
        if n == 0:
            return
        ctypes.memset(
            ctypes.addressof((ctypes.c_char * n).from_buffer(buffer)), 0, n
        )
    else:
        raise TypeError(
            f"secure_zero() requer bytearray ou memoryview, recebeu {type(buffer).__name__}"
        )


# ─── Context Manager ────────────────────────────────────────────────────────

class SecureBytes:
    """
    Wrapper RAII para dados sensíveis.

    Mantém os dados num bytearray mutável e zera-o automaticamente
    ao sair do bloco ``with`` ou quando ``wipe()`` é chamado.

    Exemplo::

        with SecureBytes(os.urandom(32)) as key:
            ciphertext = encrypt(plaintext, bytes(key))
        # key foi zerado ao sair do with
    """

    __slots__ = ("_buf", "_wiped")

    def __init__(self, data: bytes | bytearray) -> None:
        # Copiar para bytearray mutável (nunca guardar referência ao original)
        self._buf = bytearray(data)
        self._wiped = False

        # Tentar limpar o original se for bytearray
        if isinstance(data, bytearray):
            secure_zero(data)

    # ── Acesso ──

    @property
    def buffer(self) -> bytearray:
        """Devolve referência directa ao bytearray interno (mutável)."""
        if self._wiped:
            raise RuntimeError("SecureBytes já foi limpo.")
        return self._buf

    def __bytes__(self) -> bytes:
        """Converte para bytes imutável (cópia — usar com cuidado)."""
        if self._wiped:
            raise RuntimeError("SecureBytes já foi limpo.")
        return bytes(self._buf)

    def __len__(self) -> int:
        return len(self._buf)

    # ── Limpeza ──

    def wipe(self) -> None:
        """Zera o buffer imediatamente."""
        if not self._wiped:
            secure_zero(self._buf)
            self._wiped = True

    # ── Context Manager ──

    def __enter__(self) -> "SecureBytes":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.wipe()

    # ── Safety net ──

    def __del__(self) -> None:
        try:
            self.wipe()
        except Exception:
            pass  # __del__ não deve levantar excepções

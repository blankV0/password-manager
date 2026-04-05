#!/usr/bin/env python3
"""
deploy/generate_secrets.py
─────────────────────────────────────────────────────────────────────────────
Gera segredos criptograficamente seguros para o ficheiro .env de produção.

Uso:
    python deploy/generate_secrets.py

Output:
    Bloco pronto a colar no .env
─────────────────────────────────────────────────────────────────────────────
PORQUÊ:
    - secrets.token_hex(64) usa o CSPRNG do OS (/dev/urandom no Linux)
    - 64 bytes = 512 bits de entropia → impossível de bruteforçar
    - Cada run gera valores diferentes → nunca reutilizar segredos
"""

from __future__ import annotations

import secrets
import string
import sys
from datetime import datetime, timezone


def generate_jwt_secret() -> str:
    """512 bits de entropia em hexadecimal — para HS256/HS512 JWT signing."""
    return secrets.token_hex(64)


def generate_api_key() -> str:
    """Chave de API opaca — 48 bytes URL-safe base64."""
    return secrets.token_urlsafe(48)


def check_strength(secret: str, min_bits: int = 256) -> bool:
    """Verifica que o segredo tem entropia suficiente."""
    # hex encoding: 1 char = 4 bits
    return len(secret) * 4 >= min_bits


def main() -> None:
    jwt_secret = generate_jwt_secret()
    api_key = generate_api_key()
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Validar
    assert check_strength(jwt_secret, 512), "JWT secret is too weak!"

    divider = "─" * 60
    print(f"\n{divider}")
    print("  🔐  SECRETS GERADOS — Password Manager Auth Server")
    print(f"  Gerado em: {generated_at}")
    print(divider)
    print()
    print("Cole no teu ficheiro .env:")
    print()
    print(f"AUTH_JWT_SECRET={jwt_secret}")
    print()
    print("─── Opcionais ───────────────────────────────────────────")
    print(f"# API_KEY_EXAMPLE={api_key}")
    print()
    print("⚠️  AVISOS IMPORTANTES:")
    print("  • Nunca commites este output no git")
    print("  • Guarda uma cópia offline em lugar seguro")
    print("  • Rodar os secrets invalida TODOS os tokens emitidos")
    print(f"  • JWT secret: {len(jwt_secret) * 4} bits de entropia ✓")
    print(divider)
    print()


if __name__ == "__main__":
    main()

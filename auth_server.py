"""
FastAPI entrypoint for the Password Manager authentication server.

Startup behaviour
-----------------
1. Validates that AUTH_JWT_SECRET is not a weak default (blocks start in
   production mode if insecure).
2. Runs periodic cleanup of expired tokens and old audit events.
3. Disables interactive API docs (/docs, /redoc) when APP_ENV=production.

The application is designed to run behind an Nginx reverse proxy that
terminates TLS and applies additional rate-limiting.
"""

from __future__ import annotations

import logging
import os
import sys

from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.auth import auth_router, get_current_user
from src.auth.vault_api import router as vault_router
from src.auth.schemas import UserResponse

# ─────────────────────────────────────────────────────────────────────────────
# VALIDAÇÃO DE SEGURANÇA NO ARRANQUE
# Recusa iniciar em produção com configurações inseguras.
# ─────────────────────────────────────────────────────────────────────────────
_APP_ENV = os.getenv("APP_ENV", "development").lower()
_IS_PRODUCTION = _APP_ENV == "production"

_JWT_SECRET = os.getenv("AUTH_JWT_SECRET", "change-me-in-production")
_INSECURE_DEFAULTS = {"change-me-in-production", "secret", "password", "dev"}

if _IS_PRODUCTION and _JWT_SECRET in _INSECURE_DEFAULTS:
    print(
        "\n"
        "════════════════════════════════════════════════════════════\n"
        "  ❌  ERRO CRÍTICO DE SEGURANÇA — SERVIDOR NÃO INICIADO\n"
        "════════════════════════════════════════════════════════════\n"
        "  AUTH_JWT_SECRET está com o valor por defeito inseguro.\n"
        "  Em produção é obrigatório definir um segredo forte.\n\n"
        "  Gerar um segredo seguro:\n"
        "    python deploy/generate_secrets.py\n\n"
        "  Depois adicionar ao .env:\n"
        "    AUTH_JWT_SECRET=<valor_gerado>\n"
        "════════════════════════════════════════════════════════════\n",
        file=sys.stderr,
    )
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# LIFESPAN — tarefas de startup e shutdown
# ─────────────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: limpeza de tokens expirados. Shutdown: cleanup."""
    try:
        from src.auth.dependencies import get_auth_service
        service = get_auth_service()
        result = service.periodic_cleanup()
        logging.info(
            "[STARTUP] Cleanup: %d tokens removidos, %d eventos removidos",
            result["tokens_removed"],
            result["events_removed"],
        )
    except Exception as exc:
        logging.warning("[STARTUP] Cleanup falhou: %s", exc)
    yield

# ─────────────────────────────────────────────────────────────────────────────
# FASTAPI APP
# /docs e /redoc desativados em produção — expõem a estrutura completa da API.
# ─────────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Password Manager Auth Module",
    version="1.0.0",
    lifespan=lifespan,
    # Desativar documentação interativa em produção
    docs_url=None if _IS_PRODUCTION else "/docs",
    redoc_url=None if _IS_PRODUCTION else "/redoc",
    openapi_url=None if _IS_PRODUCTION else "/openapi.json",
)

# ─────────────────────────────────────────────────────────────────────────────
# CORS
# Restringir origens permitidas em produção.
# Definir CORS_ORIGINS no .env (ex: "https://teuapp.ts.net")
# ─────────────────────────────────────────────────────────────────────────────
_cors_origins_raw = os.getenv("CORS_ORIGINS", "http://localhost" if not _IS_PRODUCTION else "")
_cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(auth_router)
app.include_router(vault_router)


@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "auth"}


@app.get("/protected-example")
def protected_example(current_user: UserResponse = Depends(get_current_user)) -> dict:
    return {
        "message": "You have access to a protected route.",
        "user": current_user.model_dump(),
    }

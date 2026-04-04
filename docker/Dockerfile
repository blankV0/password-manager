# ═════════════════════════════════════════════════════════════════════════════
# Dockerfile — Password Manager Auth Server
# ─────────────────────────────────────────────────────────────────────────────
# SECURITY DECISIONS:
#   1. Multi-stage build → build tools never ship in the final image
#   2. Non-root user (appuser) → container escape has no host privileges
#   3. Read-only filesystem → malware cannot write to the container FS
#   4. Minimal base image (python:3.12-slim) → fewer CVEs than full Debian
#   5. Pin exact Python version → reproducible, auditable builds
#   6. No COPY of .env → secrets injected via Docker runtime env_file only
# ═════════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────────
# STAGE 1 — builder
# Instala as dependências e compila wheels (binary packages).
# Este stage é descartado — nenhuma ferramenta de build entra na imagem final.
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Instalar apenas o que é preciso para compilar pacotes C (argon2-cffi precisa)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copiar só o ficheiro de dependências — cache inteligente do Docker
# Se requirements.server.txt não mudar, esta layer é re-usada no próximo build
COPY docker/requirements.server.txt .

RUN pip install --upgrade pip \
    && pip wheel \
        --no-cache-dir \
        --no-deps \
        --wheel-dir /build/wheels \
        -r requirements.server.txt


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 2 — runtime
# Imagem final: apenas Python + wheels pré-compilados + código da app.
# SEM gcc, SEM libffi, SEM pip cache.
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# ── Criar utilizador sem privilégios ────────────────────────────────────────
# Correr como root dentro de um container ainda é perigoso (ex: bind mounts,
# escape via kernel exploits). Um utilizador sem privilégios mitiga isso.
RUN groupadd --system appgroup \
    && useradd --system --gid appgroup --no-create-home appuser

WORKDIR /app

# ── Instalar wheels compilados no stage anterior ────────────────────────────
COPY --from=builder /build/wheels /wheels
RUN pip install --no-cache-dir /wheels/* \
    && rm -rf /wheels

# ── Copiar apenas o código necessário para o servidor ───────────────────────
# NÃO copiamos: .env, data/, logs/, build/, dist/, requirements.txt principal
COPY src/ ./src/
COPY auth_server.py .

# ── Criar directorias de runtime com dono correto ───────────────────────────
# data/ e logs/ são montados como volumes Docker — só precisamos do mountpoint
RUN mkdir -p data logs \
    && chown -R appuser:appgroup /app

# ── Mudar para utilizador sem privilégios ───────────────────────────────────
USER appuser

# ── Expor porta INTERNA apenas ──────────────────────────────────────────────
# EXPOSE documenta a porta mas NÃO a publica no host.
# A publicação é controlada exclusivamente pelo docker-compose.yml (nginx proxy).
EXPOSE 8000

# ── Health check ────────────────────────────────────────────────────────────
# Docker marca o container como "unhealthy" se o endpoint não responder.
# Isso permite ao Compose reiniciar automaticamente em caso de falha.
HEALTHCHECK \
    --interval=30s \
    --timeout=5s \
    --start-period=15s \
    --retries=3 \
    CMD python -c "import urllib.request, sys; \
        r = urllib.request.urlopen('http://localhost:8000/health', timeout=4); \
        sys.exit(0 if r.status == 200 else 1)"

# ── Comando de arranque ─────────────────────────────────────────────────────
# --no-access-log: Nginx já regista os acessos — evitar duplicação
# --workers 1: SQLite não suporta múltiplos workers (connection locking)
#              Se mudarmos para PostgreSQL podemos aumentar para 2-4 workers
CMD ["uvicorn", "auth_server:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--no-access-log", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]

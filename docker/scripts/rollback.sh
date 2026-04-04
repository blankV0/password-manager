#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# rollback.sh — Rollback rápido para a versão anterior
# ═══════════════════════════════════════════════════════════════════
# Uso:
#   ./rollback.sh              # rollback para a imagem :rollback
#   ./rollback.sh --db         # rollback da imagem + restaurar último backup DB
#   ./rollback.sh v1.0.0       # rollback para uma tag específica
# ═══════════════════════════════════════════════════════════════════

set -euo pipefail

PROJECT_DIR="/home/blankroot/password-manager"
BACKUP_DIR="/home/blankroot/backups/auth"
COMPOSE="docker compose"
IMAGE_NAME="pm-auth"
HEALTH_URL="https://localhost/health"
DEPLOY_LOG="/home/blankroot/password-manager/logs/deploy.log"
RESTORE_DB=false
TARGET_TAG=""

# ── Parse argumentos ──────────────────────────────────────────────
for arg in "$@"; do
    case ${arg} in
        --db) RESTORE_DB=true ;;
        *)    TARGET_TAG="${arg}" ;;
    esac
done

timestamp() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(timestamp)] $1" | tee -a "${DEPLOY_LOG}"; }

cd "${PROJECT_DIR}"

log "═══════════════════════════════════════════════════════════"
log "🔄 Rollback iniciado"
log "═══════════════════════════════════════════════════════════"

# ── 1. Determinar versão alvo ─────────────────────────────────────
if [ -n "${TARGET_TAG}" ]; then
    if docker image inspect "${IMAGE_NAME}:${TARGET_TAG}" &>/dev/null; then
        log "Rollback para imagem: ${IMAGE_NAME}:${TARGET_TAG}"
        docker tag "${IMAGE_NAME}:${TARGET_TAG}" "${IMAGE_NAME}:latest"
    elif git rev-parse "${TARGET_TAG}" &>/dev/null; then
        log "Checkout da tag/commit: ${TARGET_TAG}"
        git fetch --all --tags 2>/dev/null
        git checkout "${TARGET_TAG}"
        log "A fazer rebuild..."
        ${COMPOSE} build auth 2>&1 | tail -5 | tee -a "${DEPLOY_LOG}"
    else
        log "❌ Tag/commit ${TARGET_TAG} não encontrado!"
        exit 1
    fi
else
    if docker image inspect "${IMAGE_NAME}:rollback" &>/dev/null; then
        log "Rollback para imagem: ${IMAGE_NAME}:rollback"
        docker tag "${IMAGE_NAME}:rollback" "${IMAGE_NAME}:latest"
    else
        log "❌ Sem imagem :rollback disponível!"
        echo ""
        echo "Imagens disponíveis:"
        docker images "${IMAGE_NAME}" --format '  {{.Tag}} ({{.CreatedSince}})'
        exit 1
    fi
fi

# ── 2. Restaurar DB (se --db) ────────────────────────────────────
if [ "${RESTORE_DB}" = true ]; then
    LATEST_BACKUP=$(find "${BACKUP_DIR}" -name "auth_*.db.gz" -type f -printf '%T+ %p\n' 2>/dev/null | sort -r | head -1 | awk '{print $2}')
    if [ -z "${LATEST_BACKUP}" ]; then
        log "❌ Sem backups disponíveis para restaurar!"
        exit 1
    fi
    log "A restaurar DB: ${LATEST_BACKUP}"
    bash "${PROJECT_DIR}/scripts/restore_db.sh" "${LATEST_BACKUP}" --force 2>&1 | tee -a "${DEPLOY_LOG}"
fi

# ── 3. Restart ────────────────────────────────────────────────────
log "A reiniciar containers..."
${COMPOSE} down 2>&1 | tee -a "${DEPLOY_LOG}"
${COMPOSE} up -d 2>&1 | tee -a "${DEPLOY_LOG}"

# ── 4. Health check ──────────────────────────────────────────────
sleep 10
HTTP_CODE=$(curl -sk -o /dev/null -w "%{http_code}" "${HEALTH_URL}" 2>/dev/null || echo "000")
if [ "${HTTP_CODE}" = "200" ]; then
    log "✅ Rollback concluído — serviço healthy (HTTP ${HTTP_CODE})"
else
    log "⚠️  Serviço pode não estar totalmente up (HTTP: ${HTTP_CODE})"
    log "   Verifica manualmente: docker compose ps"
fi

log "═══════════════════════════════════════════════════════════"

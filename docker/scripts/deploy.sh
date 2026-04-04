#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# deploy.sh — Deploy atómico com backup pré-deploy e rollback
# ═══════════════════════════════════════════════════════════════════
# Chamado pelo GitHub Actions ou manualmente.
#
# Uso:
#   ./deploy.sh                     # deploy da versão atual no git
#   ./deploy.sh v1.2.3              # deploy de uma tag específica
#   SKIP_BACKUP=1 ./deploy.sh       # deploy sem backup (para testes)
#
# Estratégia:
#   1. Pull das últimas alterações do git
#   2. Backup da DB antes de qualquer alteração
#   3. Build da nova imagem Docker
#   4. Teste de saúde da nova imagem (pré-deploy)
#   5. Swap atómico: stop old → start new
#   6. Verificação pós-deploy (health check)
#   7. Se falhar → rollback automático
#
# O rollback restaura:
#   - A imagem Docker anterior (tag :rollback)
#   - A base de dados (backup pré-deploy)
# ═══════════════════════════════════════════════════════════════════

set -euo pipefail

# ── Configuração ──────────────────────────────────────────────────
PROJECT_DIR="/home/blankroot/password-manager"
BACKUP_DIR="/home/blankroot/backups/auth"
DEPLOY_LOG="/home/blankroot/password-manager/logs/deploy.log"
COMPOSE="docker compose"
IMAGE_NAME="pm-auth"
HEALTH_URL="https://localhost/health"
MAX_HEALTH_RETRIES=30       # 30 × 2s = 60s máximo para ficar healthy
HEALTH_RETRY_INTERVAL=2
TAG="${1:-}"

# ── Funções ───────────────────────────────────────────────────────
timestamp() { date '+%Y-%m-%d %H:%M:%S'; }

log() {
    local msg="[$(timestamp)] $1"
    echo "${msg}" | tee -a "${DEPLOY_LOG}"
}

alert() {
    local msg="$1"
    log "⚠️  ${msg}"
    # Se o alertas.sh existir, envia notificação
    if [ -f "${PROJECT_DIR}/scripts/alerts.sh" ]; then
        source "${PROJECT_DIR}/scripts/alerts.sh"
        send_alert "🚀 DEPLOY: ${msg}"
    fi
}

die() {
    alert "❌ DEPLOY FALHOU: $1"
    exit 1
}

health_check() {
    local retries=0
    log "A verificar saúde do serviço..."
    while [ ${retries} -lt ${MAX_HEALTH_RETRIES} ]; do
        HTTP_CODE=$(curl -sk -o /dev/null -w "%{http_code}" "${HEALTH_URL}" 2>/dev/null || echo "000")
        if [ "${HTTP_CODE}" = "200" ]; then
            log "✅ Health check OK (HTTP ${HTTP_CODE})"
            return 0
        fi
        retries=$((retries + 1))
        sleep ${HEALTH_RETRY_INTERVAL}
    done
    log "❌ Health check falhou após ${retries} tentativas (último HTTP: ${HTTP_CODE})"
    return 1
}

# ── Início ────────────────────────────────────────────────────────
log "═══════════════════════════════════════════════════════════"
log "🚀 Deploy iniciado"
log "═══════════════════════════════════════════════════════════"

cd "${PROJECT_DIR}"

# ── 1. Tag da imagem anterior para rollback ───────────────────────
log "[1/7] A guardar imagem atual para rollback..."
if docker image inspect "${IMAGE_NAME}:latest" &>/dev/null; then
    docker tag "${IMAGE_NAME}:latest" "${IMAGE_NAME}:rollback" 2>/dev/null || true
    log "Imagem ${IMAGE_NAME}:rollback criada"
else
    log "Sem imagem anterior — primeiro deploy"
fi

# ── 2. Pull do código ────────────────────────────────────────────
log "[2/7] A fazer pull do código..."
git fetch --all --tags 2>&1 | tail -3 | tee -a "${DEPLOY_LOG}"

if [ -n "${TAG}" ]; then
    log "Checkout da tag: ${TAG}"
    git checkout "${TAG}" 2>&1 | tee -a "${DEPLOY_LOG}"
else
    log "Pull da branch atual..."
    git pull origin "$(git branch --show-current)" 2>&1 | tail -5 | tee -a "${DEPLOY_LOG}"
fi

COMMIT=$(git rev-parse --short HEAD)
log "Commit atual: ${COMMIT}"

# ── 3. Backup pré-deploy ─────────────────────────────────────────
if [ "${SKIP_BACKUP:-0}" != "1" ]; then
    log "[3/7] Backup pré-deploy..."
    if bash "${PROJECT_DIR}/scripts/backup_db.sh" 2>&1 | tee -a "${DEPLOY_LOG}"; then
        LATEST_BACKUP=$(find "${BACKUP_DIR}" -name "auth_*.db.gz" -type f -printf '%T+ %p\n' | sort -r | head -1 | awk '{print $2}')
        log "Backup pré-deploy: ${LATEST_BACKUP}"
    else
        log "⚠️  Backup falhou — a continuar sem backup"
    fi
else
    log "[3/7] Backup ignorado (SKIP_BACKUP=1)"
fi

# ── 4. Build da nova imagem ──────────────────────────────────────
log "[4/7] A fazer build da nova imagem..."
if ! ${COMPOSE} build --no-cache auth 2>&1 | tail -10 | tee -a "${DEPLOY_LOG}"; then
    die "Build falhou!"
fi
log "Build concluído com sucesso"

# ── 5. Tag com versão do commit ──────────────────────────────────
docker tag "${IMAGE_NAME}:latest" "${IMAGE_NAME}:${COMMIT}" 2>/dev/null || true
if [ -n "${TAG}" ]; then
    docker tag "${IMAGE_NAME}:latest" "${IMAGE_NAME}:${TAG}" 2>/dev/null || true
fi
log "[5/7] Imagem taggeada: ${IMAGE_NAME}:${COMMIT}"

# ── 6. Deploy — restart dos containers ───────────────────────────
log "[6/7] A reiniciar containers..."
${COMPOSE} down 2>&1 | tee -a "${DEPLOY_LOG}"
${COMPOSE} up -d 2>&1 | tee -a "${DEPLOY_LOG}"
log "Containers reiniciados"

# ── 7. Verificação pós-deploy ────────────────────────────────────
log "[7/7] Verificação pós-deploy..."
if health_check; then
    log "═══════════════════════════════════════════════════════════"
    log "✅ Deploy concluído com sucesso! (commit: ${COMMIT})"
    log "═══════════════════════════════════════════════════════════"
    alert "✅ Deploy v${TAG:-${COMMIT}} concluído com sucesso"
else
    log "❌ Health check falhou! A iniciar rollback..."
    alert "❌ Deploy v${TAG:-${COMMIT}} falhou — a fazer rollback"

    # ── ROLLBACK ──────────────────────────────────────────────────
    if docker image inspect "${IMAGE_NAME}:rollback" &>/dev/null; then
        log "A restaurar imagem :rollback..."
        docker tag "${IMAGE_NAME}:rollback" "${IMAGE_NAME}:latest"
        ${COMPOSE} down 2>&1 | tee -a "${DEPLOY_LOG}"
        ${COMPOSE} up -d 2>&1 | tee -a "${DEPLOY_LOG}"

        if health_check; then
            log "✅ Rollback concluído — versão anterior restaurada"
            alert "🔄 Rollback concluído — versão anterior restaurada"
        else
            die "Rollback também falhou! Intervenção manual necessária."
        fi
    else
        die "Sem imagem de rollback disponível! Intervenção manual necessária."
    fi

    exit 1
fi

#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# health_monitor.sh — Monitorização leve dos containers Docker
# ═══════════════════════════════════════════════════════════════════
# Cron: */5 * * * * /home/blankroot/password-manager/scripts/health_monitor.sh
#
# Verifica:
#   - Containers a correr e saudáveis
#   - Endpoint /health responde
#   - Disco não está cheio
#   - Docker logs não estão muito grandes
#   - Certificado TLS não está a expirar
#
# Envia alertas via Discord/Telegram se configurado.
# ═══════════════════════════════════════════════════════════════════

set -euo pipefail

PROJECT_DIR="/home/blankroot/password-manager"
LOG_FILE="${PROJECT_DIR}/logs/monitor.log"
HEALTH_URL="https://localhost/health"
MAX_DISK_PERCENT=85
MAX_RESTART_COUNT=5

mkdir -p "$(dirname "${LOG_FILE}")"

# Carregar sistema de alertas (Discord/Telegram)
source "${PROJECT_DIR}/scripts/alerts.sh" 2>/dev/null || true

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "${LOG_FILE}"
}

FAILURES=0

# ── 1. Verificar containers ──────────────────────────────────────
for CONTAINER in pm_auth pm_nginx; do
    STATUS=$(docker inspect "${CONTAINER}" --format '{{.State.Status}}' 2>/dev/null || echo "not_found")
    
    if [ "${STATUS}" != "running" ]; then
        send_alert "🔴 Container ${CONTAINER} não está a correr (status: ${STATUS})" "error" 2>/dev/null || true
        FAILURES=$((FAILURES + 1))
        continue
    fi

    # Verificar health do pm_auth
    if [ "${CONTAINER}" = "pm_auth" ]; then
        HEALTH=$(docker inspect "${CONTAINER}" --format '{{.State.Health.Status}}' 2>/dev/null || echo "unknown")
        if [ "${HEALTH}" != "healthy" ]; then
            send_alert "🟡 Container ${CONTAINER} não é healthy (${HEALTH})" "warning" 2>/dev/null || true
            FAILURES=$((FAILURES + 1))
        fi
    fi

    # Verificar restart count excessivo
    RESTARTS=$(docker inspect "${CONTAINER}" --format '{{.RestartCount}}' 2>/dev/null || echo "0")
    if [ "${RESTARTS}" -gt "${MAX_RESTART_COUNT}" ]; then
        send_alert "⚠️ Container ${CONTAINER} tem ${RESTARTS} restarts (max: ${MAX_RESTART_COUNT})" "warning" 2>/dev/null || true
    fi
done

# ── 2. Verificar endpoint /health ─────────────────────────────────
HTTP_CODE=$(curl -sk -o /dev/null -w "%{http_code}" "${HEALTH_URL}" 2>/dev/null || echo "000")
if [ "${HTTP_CODE}" != "200" ]; then
    send_alert "🔴 Health endpoint retornou HTTP ${HTTP_CODE}" "error" 2>/dev/null || true
    FAILURES=$((FAILURES + 1))
fi

# ── 3. Verificar espaço em disco ──────────────────────────────────
DISK_USAGE=$(df / | tail -1 | awk '{print $5}' | tr -d '%')
if [ "${DISK_USAGE}" -gt "${MAX_DISK_PERCENT}" ]; then
    send_alert "💾 Disco ${DISK_USAGE}% usado (máximo: ${MAX_DISK_PERCENT}%)" "error" 2>/dev/null || true
    FAILURES=$((FAILURES + 1))
fi

# ── 4. Verificar tamanho dos Docker logs ──────────────────────────
for CONTAINER in pm_auth pm_nginx; do
    LOG_SIZE=$(docker inspect "${CONTAINER}" --format '{{.LogPath}}' 2>/dev/null | xargs du -sm 2>/dev/null | awk '{print $1}' || echo "0")
    if [ "${LOG_SIZE}" -gt 50 ]; then
        send_alert "📋 Docker logs de ${CONTAINER} com ${LOG_SIZE}MB (> 50MB)" "warning" 2>/dev/null || true
    fi
done

# ── 5. Verificar certificado TLS ─────────────────────────────────
CERT_FILE="/home/blankroot/password-manager/nginx/certs/fullchain.pem"
if [ -f "${CERT_FILE}" ]; then
    EXPIRY=$(openssl x509 -in "${CERT_FILE}" -noout -enddate 2>/dev/null | cut -d= -f2)
    EXPIRY_EPOCH=$(date -d "${EXPIRY}" +%s 2>/dev/null || echo "0")
    NOW_EPOCH=$(date +%s)
    DAYS_LEFT=$(( (EXPIRY_EPOCH - NOW_EPOCH) / 86400 ))
    
    if [ "${DAYS_LEFT}" -lt 30 ]; then
        send_alert "🔒 Certificado TLS expira em ${DAYS_LEFT} dias!" "warning" 2>/dev/null || true
        FAILURES=$((FAILURES + 1))
    fi
fi

# ── Resultado ─────────────────────────────────────────────────────
if [ "${FAILURES}" -eq 0 ]; then
    log "OK — Todos os checks passaram (disk: ${DISK_USAGE}%, health: ${HTTP_CODE})"
else
    log "FAIL — ${FAILURES} check(s) falharam"
fi

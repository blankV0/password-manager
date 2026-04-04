#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# backup_offsite.sh — Sincronizar backups para localização remota
# ═══════════════════════════════════════════════════════════════════
# Cron: 30 */6 * * * (30 min após o backup local)
#
# Suporta:
#   - rsync para outro PC/NAS na rede (ex: via SSH)
#   - rclone para S3-compatible (Backblaze B2, Wasabi, MinIO)
#
# Configuração em: /home/blankroot/.config/pm-alerts.conf
#   OFFSITE_METHOD="rsync"    # ou "rclone"
#   OFFSITE_TARGET="user@nas:/backups/pm/"
#   RCLONE_REMOTE="b2:pm-backups/auth/"
# ═══════════════════════════════════════════════════════════════════

set -euo pipefail

PROJECT_DIR="/home/blankroot/password-manager"
BACKUP_DIR="/home/blankroot/backups/auth"
LOG_FILE="${PROJECT_DIR}/logs/backup_offsite.log"
CONFIG_FILE="/home/blankroot/.config/pm-alerts.conf"

# Carregar alerts
source "${PROJECT_DIR}/scripts/alerts.sh" 2>/dev/null || true

timestamp() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(timestamp)] $1" | tee -a "${LOG_FILE}"; }

# ── Carregar configuração ─────────────────────────────────────────
if [ -f "${CONFIG_FILE}" ]; then
    source "${CONFIG_FILE}"
fi

OFFSITE_METHOD="${OFFSITE_METHOD:-none}"
OFFSITE_TARGET="${OFFSITE_TARGET:-}"
RCLONE_REMOTE="${RCLONE_REMOTE:-}"

if [ "${OFFSITE_METHOD}" = "none" ]; then
    log "Offsite backup não configurado. Ver ${CONFIG_FILE}"
    log "Opções: OFFSITE_METHOD=rsync|rclone"
    exit 0
fi

log "═══════════════════════════════════════════════════════════"
log "📤 Backup offsite iniciado (${OFFSITE_METHOD})"

# ── Verificar que existem backups ─────────────────────────────────
BACKUP_COUNT=$(find "${BACKUP_DIR}" -name "auth_*.db.gz" -type f 2>/dev/null | wc -l)
if [ "${BACKUP_COUNT}" -eq 0 ]; then
    log "❌ Sem backups locais para sincronizar!"
    send_alert "❌ Backup offsite: sem backups locais!" "error"
    exit 1
fi

log "Backups locais encontrados: ${BACKUP_COUNT}"

# ── Método: rsync ─────────────────────────────────────────────────
if [ "${OFFSITE_METHOD}" = "rsync" ]; then
    if [ -z "${OFFSITE_TARGET}" ]; then
        log "❌ OFFSITE_TARGET não definido!"
        exit 1
    fi

    log "rsync → ${OFFSITE_TARGET}"
    if rsync -avz --progress \
        "${BACKUP_DIR}/" \
        "${OFFSITE_TARGET}" \
        2>&1 | tail -5 | tee -a "${LOG_FILE}"; then
        log "✅ Offsite sync concluído (rsync)"
        send_alert "✅ Backup offsite concluído (${BACKUP_COUNT} ficheiros via rsync)" "success"
    else
        log "❌ rsync falhou!"
        send_alert "❌ Backup offsite falhou (rsync)" "error"
        exit 1
    fi
fi

# ── Método: rclone (S3-compatible) ────────────────────────────────
if [ "${OFFSITE_METHOD}" = "rclone" ]; then
    if ! command -v rclone &>/dev/null; then
        log "❌ rclone não instalado! Instalar: curl https://rclone.org/install.sh | sudo bash"
        exit 1
    fi

    if [ -z "${RCLONE_REMOTE}" ]; then
        log "❌ RCLONE_REMOTE não definido!"
        exit 1
    fi

    log "rclone sync → ${RCLONE_REMOTE}"
    if rclone sync \
        "${BACKUP_DIR}/" \
        "${RCLONE_REMOTE}" \
        --transfers 2 \
        --checkers 4 \
        --log-level INFO \
        2>&1 | tail -5 | tee -a "${LOG_FILE}"; then
        log "✅ Offsite sync concluído (rclone)"
        send_alert "✅ Backup offsite concluído (${BACKUP_COUNT} ficheiros via rclone)" "success"
    else
        log "❌ rclone sync falhou!"
        send_alert "❌ Backup offsite falhou (rclone)" "error"
        exit 1
    fi
fi

# ── Verificação de integridade (último backup) ────────────────────
LATEST=$(find "${BACKUP_DIR}" -name "auth_*.db.gz" -type f -printf '%T+ %p\n' | sort -r | head -1 | awk '{print $2}')
if [ -n "${LATEST}" ]; then
    TEMP_DB="/tmp/verify_backup_$$.db"
    gunzip -c "${LATEST}" > "${TEMP_DB}" 2>/dev/null
    INTEGRITY=$(sqlite3 "${TEMP_DB}" "PRAGMA integrity_check;" 2>&1)
    USERS=$(sqlite3 "${TEMP_DB}" "SELECT COUNT(*) FROM users;" 2>/dev/null || echo "?")
    rm -f "${TEMP_DB}"

    if [ "${INTEGRITY}" = "ok" ]; then
        log "✅ Integridade OK: ${LATEST} (${USERS} users)"
    else
        log "❌ Backup corrompido: ${LATEST}"
        send_alert "❌ Backup corrompido: ${LATEST}" "error"
    fi
fi

log "═══════════════════════════════════════════════════════════"

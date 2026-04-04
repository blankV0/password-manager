#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# backup_db.sh — Backup automático do SQLite auth.db
# ═══════════════════════════════════════════════════════════════════
# Uso: ./backup_db.sh
# Cron: 0 */6 * * * /home/blankroot/password-manager/scripts/backup_db.sh
#
# Estratégia:
#   - Usa sqlite3 .backup (online, sem lock no escritor)
#   - Mantém últimos 14 backups (7 dias × 2/dia = cobertura de 7 dias)
#   - Comprime com gzip (~90% redução)
#   - Verifica integridade do backup
# ═══════════════════════════════════════════════════════════════════

set -euo pipefail

# ── Configuração ──────────────────────────────────────────────────
CONTAINER="pm_auth"
DB_PATH="/app/data/auth.db"
BACKUP_DIR="/home/blankroot/backups/auth"
MAX_BACKUPS=14
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/auth_${TIMESTAMP}.db"

# ── Criar directório de backup ────────────────────────────────────
mkdir -p "${BACKUP_DIR}"

# ── Verificar que o container está a correr ───────────────────────
if ! docker inspect "${CONTAINER}" --format '{{.State.Running}}' 2>/dev/null | grep -q "true"; then
    echo "[ERRO] Container ${CONTAINER} não está a correr!" >&2
    exit 1
fi

# ── Fazer backup online do SQLite ─────────────────────────────────
# Usa sqlite3 .backup via python dentro do container (copia consistente)
# O output vai para stdout em base64 para evitar problemas de FS read-only
echo "[BACKUP] A copiar auth.db do container ${CONTAINER}..."
docker exec "${CONTAINER}" python3 -c "
import sqlite3, sys, base64
src = sqlite3.connect('${DB_PATH}')
dst = sqlite3.connect('/tmp/backup.db')
src.backup(dst)
dst.close()
src.close()
with open('/tmp/backup.db', 'rb') as f:
    sys.stdout.buffer.write(f.read())
" > "${BACKUP_FILE}"

# Verificar que o ficheiro não está vazio
if [ ! -s "${BACKUP_FILE}" ]; then
    echo "[ERRO] Backup vazio!" >&2
    rm -f "${BACKUP_FILE}"
    exit 1
fi

# ── Verificar integridade ─────────────────────────────────────────
echo "[BACKUP] A verificar integridade..."
INTEGRITY=$(sqlite3 "${BACKUP_FILE}" "PRAGMA integrity_check;" 2>&1)
if [ "${INTEGRITY}" != "ok" ]; then
    echo "[ERRO] Backup corrompido! integrity_check: ${INTEGRITY}" >&2
    rm -f "${BACKUP_FILE}"
    exit 1
fi

# Contar registos para validação
USERS=$(sqlite3 "${BACKUP_FILE}" "SELECT COUNT(*) FROM users;" 2>/dev/null)
TOKENS=$(sqlite3 "${BACKUP_FILE}" "SELECT COUNT(*) FROM refresh_tokens;" 2>/dev/null)
echo "[BACKUP] Backup OK: ${USERS} users, ${TOKENS} refresh_tokens"

# ── Comprimir ─────────────────────────────────────────────────────
gzip "${BACKUP_FILE}"
BACKUP_SIZE=$(du -h "${BACKUP_FILE}.gz" | cut -f1)
echo "[BACKUP] Comprimido: ${BACKUP_FILE}.gz (${BACKUP_SIZE})"

# ── Rotação — manter apenas os últimos N backups ──────────────────
BACKUP_COUNT=$(find "${BACKUP_DIR}" -name "auth_*.db.gz" -type f | wc -l)
if [ "${BACKUP_COUNT}" -gt "${MAX_BACKUPS}" ]; then
    EXCESS=$((BACKUP_COUNT - MAX_BACKUPS))
    find "${BACKUP_DIR}" -name "auth_*.db.gz" -type f -printf '%T+ %p\n' \
        | sort | head -n "${EXCESS}" | awk '{print $2}' \
        | xargs rm -f
    echo "[BACKUP] Removidos ${EXCESS} backups antigos (mantidos ${MAX_BACKUPS})"
fi

# ── Limpar ────────────────────────────────────────────────────────
docker exec "${CONTAINER}" rm -f /tmp/backup.db 2>/dev/null || true

echo "[BACKUP] ✅ Concluído: $(date)"

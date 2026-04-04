#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# restore_db.sh — Restaurar backup do SQLite auth.db
# ═══════════════════════════════════════════════════════════════════
# Uso: ./restore_db.sh [ficheiro_backup.db.gz]
#   Se nenhum ficheiro for dado, lista os backups disponíveis.
# ═══════════════════════════════════════════════════════════════════

set -euo pipefail

CONTAINER="pm_auth"
BACKUP_DIR="/home/blankroot/backups/auth"

if [ $# -eq 0 ]; then
    echo "Backups disponíveis:"
    echo "──────────────────────────────────────────"
    ls -lh "${BACKUP_DIR}"/auth_*.db.gz 2>/dev/null || echo "  Nenhum backup encontrado."
    echo ""
    echo "Uso: $0 <ficheiro_backup.db.gz>"
    exit 0
fi

BACKUP_FILE="$1"

if [ ! -f "${BACKUP_FILE}" ]; then
    # Tentar no directório de backup
    if [ -f "${BACKUP_DIR}/${BACKUP_FILE}" ]; then
        BACKUP_FILE="${BACKUP_DIR}/${BACKUP_FILE}"
    else
        echo "[ERRO] Ficheiro não encontrado: ${BACKUP_FILE}" >&2
        exit 1
    fi
fi

echo "╔════════════════════════════════════════════════╗"
echo "║  ⚠️  ATENÇÃO: RESTAURO DE BASE DE DADOS       ║"
echo "╠════════════════════════════════════════════════╣"
echo "║  Isto vai SUBSTITUIR a base de dados atual!    ║"
echo "║  Backup a restaurar: $(basename "${BACKUP_FILE}")"
echo "╚════════════════════════════════════════════════╝"
echo ""
read -p "Continuar? (escreve 'sim' para confirmar): " CONFIRM
if [ "${CONFIRM}" != "sim" ]; then
    echo "Cancelado."
    exit 0
fi

# ── Descomprimir para temporário ──────────────────────────────────
TEMP_DB="/tmp/restore_auth.db"
echo "[RESTORE] A descomprimir..."
gunzip -c "${BACKUP_FILE}" > "${TEMP_DB}"

# ── Verificar integridade ─────────────────────────────────────────
INTEGRITY=$(sqlite3 "${TEMP_DB}" "PRAGMA integrity_check;" 2>&1)
if [ "${INTEGRITY}" != "ok" ]; then
    echo "[ERRO] Backup corrompido! ${INTEGRITY}" >&2
    rm -f "${TEMP_DB}"
    exit 1
fi

USERS=$(sqlite3 "${TEMP_DB}" "SELECT COUNT(*) FROM users;")
echo "[RESTORE] Backup válido: ${USERS} users"

# ── Parar container, restaurar, reiniciar ─────────────────────────
echo "[RESTORE] A parar ${CONTAINER}..."
docker stop "${CONTAINER}"

# Copiar para o volume Docker
VOLUME_PATH=$(docker volume inspect password-manager_auth_data --format '{{.Mountpoint}}')
echo "[RESTORE] A copiar para ${VOLUME_PATH}/auth.db..."
cp "${TEMP_DB}" "${VOLUME_PATH}/auth.db"

echo "[RESTORE] A reiniciar stack..."
cd /home/blankroot/password-manager
docker compose up -d

# ── Esperar health check ──────────────────────────────────────────
echo "[RESTORE] A aguardar health check..."
sleep 10
HEALTH=$(curl -sk https://localhost/health 2>/dev/null || echo "FAIL")
echo "[RESTORE] Health: ${HEALTH}"

# ── Cleanup ───────────────────────────────────────────────────────
rm -f "${TEMP_DB}"
echo "[RESTORE] ✅ Restauro concluído!"

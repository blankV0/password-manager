#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# alerts.sh — Sistema de alertas via Discord webhook
# ═══════════════════════════════════════════════════════════════════
# Chamado por outros scripts (health_monitor.sh, backup_db.sh, deploy.sh)
#
# Configuração:
#   1. Criar webhook no Discord: Server Settings → Integrations → Webhooks
#   2. Copiar o URL do webhook
#   3. Guardar em: /home/blankroot/.config/pm-alerts.conf
#      DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
#
# Uso direto:
#   source scripts/alerts.sh
#   send_alert "Container pm_auth está down!"
#   send_alert "✅ Backup concluído" "info"
# ═══════════════════════════════════════════════════════════════════

ALERT_CONFIG="/home/blankroot/.config/pm-alerts.conf"
HOSTNAME=$(hostname 2>/dev/null || echo "unknown")

# ── Carregar configuração ─────────────────────────────────────────
if [ -f "${ALERT_CONFIG}" ]; then
    # shellcheck source=/dev/null
    source "${ALERT_CONFIG}"
fi

# ── Cores por severidade (Discord embed colors) ──────────────────
_alert_color() {
    case "${1:-error}" in
        info)    echo "3447003"  ;;  # azul
        warning) echo "16776960" ;;  # amarelo
        error)   echo "15158332" ;;  # vermelho
        success) echo "3066993"  ;;  # verde
        *)       echo "10070709" ;;  # cinza
    esac
}

# ═══════════════════════════════════════════════════════════════════
# send_alert — Envia alerta para Discord
#
# Parâmetros:
#   $1 — Mensagem (obrigatório)
#   $2 — Severidade: info, warning, error, success (default: error)
# ═══════════════════════════════════════════════════════════════════
send_alert() {
    local message="${1:?Mensagem obrigatória}"
    local severity="${2:-error}"
    local color
    color=$(_alert_color "${severity}")

    # Sempre logar localmente
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [${severity}] ${message}" \
        >> /home/blankroot/password-manager/logs/alerts.log 2>/dev/null || true

    # Se não há webhook, só loga
    if [ -z "${DISCORD_WEBHOOK_URL:-}" ]; then
        return 0
    fi

    # Enviar para Discord
    local payload
    payload=$(cat <<ENDJSON
{
  "embeds": [{
    "title": "🖥️ Password Manager — ${HOSTNAME}",
    "description": "${message}",
    "color": ${color},
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "footer": {"text": "PM Monitor • ${HOSTNAME}"}
  }]
}
ENDJSON
)

    # Enviar (timeout de 10s, silencioso)
    curl -s -o /dev/null -w '' \
        -H "Content-Type: application/json" \
        -d "${payload}" \
        --max-time 10 \
        "${DISCORD_WEBHOOK_URL}" 2>/dev/null || true
}

# ═══════════════════════════════════════════════════════════════════
# send_alert_telegram — Alternativa: Telegram Bot
#
# Configuração em pm-alerts.conf:
#   TELEGRAM_BOT_TOKEN="123456:ABC..."
#   TELEGRAM_CHAT_ID="-100123456789"
# ═══════════════════════════════════════════════════════════════════
send_alert_telegram() {
    local message="${1:?Mensagem obrigatória}"

    if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] || [ -z "${TELEGRAM_CHAT_ID:-}" ]; then
        return 0
    fi

    curl -s -o /dev/null \
        --max-time 10 \
        "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_CHAT_ID}" \
        -d "text=🖥️ ${HOSTNAME}: ${message}" \
        -d "parse_mode=HTML" 2>/dev/null || true
}

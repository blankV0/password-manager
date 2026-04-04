#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# harden_server.sh — Hardening do servidor Ubuntu
# ═══════════════════════════════════════════════════════════════════
# Corre como root: sudo bash harden_server.sh
#
# O que faz:
#   1. Desativa login SSH com password (só chaves)
#   2. Desativa login SSH como root
#   3. Instala e configura fail2ban
#   4. Ajusta permissões de ficheiros sensíveis
#   5. Configura unattended-upgrades para segurança
# ═══════════════════════════════════════════════════════════════════

set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "[ERRO] Este script precisa de ser executado como root (sudo)." >&2
    exit 1
fi

echo "╔════════════════════════════════════════════════╗"
echo "║       🔐 SERVER HARDENING — Ubuntu 24.04       ║"
echo "╚════════════════════════════════════════════════╝"

# ── 1. SSH Hardening ──────────────────────────────────────────────
echo ""
echo "═══ 1. SSH Hardening ═══"

SSHD_CONFIG="/etc/ssh/sshd_config"
SSHD_HARDENED="/etc/ssh/sshd_config.d/hardening.conf"

cat > "${SSHD_HARDENED}" << 'EOF'
# Password Manager Server — SSH Hardening
# Gerado automaticamente por harden_server.sh

# Desativar login com password (só chaves SSH)
PasswordAuthentication no
ChallengeResponseAuthentication no

# Desativar login root
PermitRootLogin no

# Apenas utilizadores permitidos
AllowUsers blankroot

# Desativar X11 forwarding (não necessário num servidor)
X11Forwarding no

# Máximo de tentativas de autenticação
MaxAuthTries 3

# Timeout para login (segundos)
LoginGraceTime 30

# Fechar conexões ociosas
ClientAliveInterval 300
ClientAliveCountMax 2
EOF

echo "  ✅ Configuração SSH aplicada em ${SSHD_HARDENED}"

# Validar configuração antes de aplicar
if sshd -t 2>/dev/null; then
    systemctl reload sshd
    echo "  ✅ SSHD recarregado com sucesso"
else
    echo "  ⚠️  Configuração SSH inválida — a reverter"
    rm -f "${SSHD_HARDENED}"
    exit 1
fi

# ── 2. Fail2ban ───────────────────────────────────────────────────
echo ""
echo "═══ 2. Fail2ban ═══"

if ! command -v fail2ban-client &>/dev/null; then
    apt-get update -qq
    apt-get install -y -qq fail2ban
fi

cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
# Ban por 1 hora após 5 falhas em 10 minutos
bantime = 3600
findtime = 600
maxretry = 5
# Usar systemd para ler logs
backend = systemd
# Ignorar rede Tailscale (100.64.0.0/10) e localhost
ignoreip = 127.0.0.1/8 ::1 100.64.0.0/10

[sshd]
enabled = true
port = ssh
filter = sshd
maxretry = 3
bantime = 7200
EOF

systemctl enable fail2ban --quiet
systemctl restart fail2ban
echo "  ✅ Fail2ban instalado e configurado"
echo "  → Ban SSH: 3 falhas = 2h ban"
echo "  → Tailscale (100.64.0.0/10) ignorado"

# ── 3. Permissões de ficheiros ────────────────────────────────────
echo ""
echo "═══ 3. Permissões de ficheiros sensíveis ═══"

PM_DIR="/home/blankroot/password-manager"

if [ -d "${PM_DIR}" ]; then
    # .env só legível pelo dono
    [ -f "${PM_DIR}/.env" ] && chmod 600 "${PM_DIR}/.env" && echo "  ✅ .env → 600"

    # Chaves privadas TLS
    [ -f "${PM_DIR}/nginx/certs/privkey.pem" ] && chmod 600 "${PM_DIR}/nginx/certs/privkey.pem" && echo "  ✅ privkey.pem → 600"

    # Scripts executáveis
    [ -d "${PM_DIR}/scripts" ] && chmod 750 "${PM_DIR}/scripts/"*.sh 2>/dev/null && echo "  ✅ scripts/ → 750"

    # Directório de backups
    mkdir -p /home/blankroot/backups/auth
    chmod 700 /home/blankroot/backups/auth
    chown blankroot:blankroot /home/blankroot/backups/auth
    echo "  ✅ backups/ → 700"
fi

# ── 4. Unattended Upgrades (segurança automática) ─────────────────
echo ""
echo "═══ 4. Atualizações automáticas de segurança ═══"

if ! dpkg -l | grep -q unattended-upgrades; then
    apt-get install -y -qq unattended-upgrades
fi

# Ativar apenas security updates automáticos
cat > /etc/apt/apt.conf.d/50unattended-upgrades << 'UEOF'
Unattended-Upgrade::Allowed-Origins {
    "${distro_id}:${distro_codename}-security";
};
Unattended-Upgrade::AutoFixInterruptedDpkg "true";
Unattended-Upgrade::Remove-Unused-Kernel-Packages "true";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
UEOF

cat > /etc/apt/apt.conf.d/20auto-upgrades << 'AEOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
AEOF

echo "  ✅ Unattended-upgrades configurado (só patches de segurança)"

# ── 5. Resumo ─────────────────────────────────────────────────────
echo ""
echo "╔════════════════════════════════════════════════╗"
echo "║       ✅ HARDENING COMPLETO                     ║"
echo "╠════════════════════════════════════════════════╣"
echo "║  SSH: só chaves, sem root, 3 tentativas max    ║"
echo "║  Fail2ban: 3 falhas SSH = 2h ban              ║"
echo "║  Permissões: .env 600, certs 600              ║"
echo "║  Updates: security patches automáticos         ║"
echo "╚════════════════════════════════════════════════╝"
echo ""
echo "⚠️  IMPORTANTE: Confirma que tens acesso SSH por chave"
echo "   ANTES de fechar esta sessão! O login por password"
echo "   foi desativado."

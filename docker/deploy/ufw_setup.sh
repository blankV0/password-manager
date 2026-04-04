#!/usr/bin/env bash
# ═════════════════════════════════════════════════════════════════════════════
# deploy/ufw_setup.sh — Configuração de Firewall (UFW) para Ubuntu Server
# ─────────────────────────────────────────────────────────────────────────────
#
# EXECUTAR NO SERVIDOR UBUNTU (não na máquina Windows de desenvolvimento):
#   chmod +x deploy/ufw_setup.sh
#   sudo ./deploy/ufw_setup.sh
#
# O QUE ESTE SCRIPT FAZ:
#   1. Configura o UFW com política deny-all por defeito
#   2. Permite SSH (porta 22) — SEMPRE antes de activar UFW (senão ficas locked out)
#   3. Permite Tailscale (porta UDP 41641)
#   4. Permite HTTPS (443) e HTTP (80, para redirect)
#   5. CORRIGE o problema do Docker contornar o UFW via iptables directo
#
# PORQUÊ O UFW+DOCKER É PROBLEMÁTICO:
#   O Docker modifica iptables directamente para expor portas. Isto significa
#   que mesmo que o UFW bloqueie a porta 443, se o Docker está a mapear a
#   porta, o tráfego PASSA MESMO ASSIM. A solução é configurar o Docker
#   para NÃO modificar iptables, ou usar a correção abaixo.
#
# ═════════════════════════════════════════════════════════════════════════════

set -euo pipefail

# ─── Verificar que está a correr como root ───────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    echo "❌  Este script precisa de correr como root (sudo)."
    exit 1
fi

echo "════════════════════════════════════════════════════"
echo "  🔒  Configuração UFW — Password Manager Server"
echo "════════════════════════════════════════════════════"
echo ""

# ─── PASSO 1: Política por defeito ───────────────────────────────────────────
echo "[1/6] Definir política por defeito: DENY tudo que entra, ALLOW tudo que sai..."
ufw default deny incoming
ufw default allow outgoing
echo "      ✓ deny incoming / allow outgoing"
echo ""

# ─── PASSO 2: SSH — CRÍTICO, fazer PRIMEIRO ──────────────────────────────────
echo "[2/6] Permitir SSH (porta 22)..."
echo "      ⚠️  Se não fizermos isto AGORA, ficamos sem acesso ao servidor."
ufw allow ssh
echo "      ✓ SSH (22/tcp) permitido"
echo ""

# ─── PASSO 3: Tailscale ──────────────────────────────────────────────────────
echo "[3/6] Permitir Tailscale (WireGuard UDP 41641)..."
ufw allow 41641/udp comment "Tailscale WireGuard"
echo "      ✓ Tailscale (41641/udp) permitido"
echo ""

# ─── PASSO 4: Web (HTTPS + HTTP redirect) ────────────────────────────────────
echo "[4/6] Permitir HTTPS (443) e HTTP redirect (80)..."
ufw allow 443/tcp comment "HTTPS (Nginx)"
ufw allow 80/tcp  comment "HTTP redirect para HTTPS"
echo "      ✓ 443/tcp e 80/tcp permitidos"
echo ""

# ─── PASSO 5: Activar UFW ────────────────────────────────────────────────────
echo "[5/6] Activar UFW..."
ufw --force enable
echo "      ✓ UFW activado"
echo ""

# ─── PASSO 6: CORRECÇÃO Docker + UFW ─────────────────────────────────────────
echo "[6/6] Corrigir interação Docker + UFW..."
echo ""
echo "  ══════════════════════════════════════════════════════════════"
echo "  ⚠️  PROBLEMA CRÍTICO: Docker bypassa UFW"
echo "  ══════════════════════════════════════════════════════════════"
echo "  O Docker modifica iptables directamente, ignorando o UFW."
echo "  Isso significa que portas expostas nos containers ficam"
echo "  acessíveis mesmo que o UFW as bloqueie."
echo ""
echo "  SOLUÇÃO — editar /etc/docker/daemon.json:"
echo ""

# Criar/atualizar daemon.json do Docker
DAEMON_JSON="/etc/docker/daemon.json"

if [[ -f "$DAEMON_JSON" ]]; then
    echo "  (Ficheiro $DAEMON_JSON já existe — fazendo backup)"
    cp "$DAEMON_JSON" "${DAEMON_JSON}.bak.$(date +%Y%m%d%H%M%S)"
fi

# Escrever configuração que desactiva a manipulação de iptables pelo Docker
cat > "$DAEMON_JSON" << 'EOF'
{
  "iptables": false,
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF

echo "      ✓ /etc/docker/daemon.json configurado (iptables: false)"
echo ""
echo "  ⚠️  NECESSÁRIO: reiniciar o Docker para aplicar a configuração:"
echo "     sudo systemctl restart docker"
echo ""
echo "  ⚠️  DEPOIS do restart, o routing interno do Docker usa a sua"
echo "      própria chain — o UFW agora controla o acesso externo."
echo ""

# ─── RESUMO ──────────────────────────────────────────────────────────────────
echo "════════════════════════════════════════════════════"
echo "  ✅  UFW configurado com sucesso"
echo "════════════════════════════════════════════════════"
echo ""
ufw status verbose
echo ""
echo "PRÓXIMO PASSO:"
echo "  sudo systemctl restart docker"
echo "  docker compose up -d"
echo ""

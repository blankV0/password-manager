#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# bootstrap.sh — Setup completo de um novo servidor
# ═══════════════════════════════════════════════════════════════════
# Disaster Recovery: restaurar TUDO num servidor Ubuntu limpo.
#
# Pré-requisitos:
#   - Ubuntu 22.04+ LTS (clean install)
#   - Acesso root ou sudo
#   - Internet
#
# Uso:
#   curl -sSL https://raw.githubusercontent.com/blankV0/password-manager/main/scripts/bootstrap.sh | bash
#   # OU
#   scp bootstrap.sh user@newserver:~ && ssh user@newserver 'bash bootstrap.sh'
#
# O que faz:
#   1. Instala Docker + Docker Compose
#   2. Instala Tailscale
#   3. Instala ferramentas (fail2ban, sqlite3, unattended-upgrades)
#   4. Configura utilizador (se necessário)
#   5. Clona o repositório
#   6. Pede o .env (secrets)
#   7. Restaura backup (se fornecido)
#   8. Faz build e deploy
#   9. Configura SSH hardening + fail2ban
#   10. Configura cron jobs
# ═══════════════════════════════════════════════════════════════════

set -euo pipefail

# ── Cores ─────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC}  $1"; }
success() { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error()   { echo -e "${RED}[ERRO]${NC}  $1"; }

# ── Verificações ──────────────────────────────────────────────────
if [ "$(id -u)" -eq 0 ]; then
    error "Não correr como root! Usar um utilizador com sudo."
    exit 1
fi

INSTALL_USER=$(whoami)
PROJECT_DIR="/home/${INSTALL_USER}/password-manager"
BACKUP_DIR="/home/${INSTALL_USER}/backups/auth"

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  🔧 Password Manager — Bootstrap de Servidor"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "  Utilizador: ${INSTALL_USER}"
echo "  Projecto:   ${PROJECT_DIR}"
echo ""
read -p "Continuar? (y/N) " -r
echo
[[ $REPLY =~ ^[Yy]$ ]] || exit 0

# ═══════════════════════════════════════════════════════════════════
# 1. DEPENDÊNCIAS DO SISTEMA
# ═══════════════════════════════════════════════════════════════════
info "A instalar dependências do sistema..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git \
    sqlite3 \
    fail2ban \
    unattended-upgrades \
    ufw \
    gzip

success "Dependências instaladas"

# ═══════════════════════════════════════════════════════════════════
# 2. DOCKER
# ═══════════════════════════════════════════════════════════════════
if command -v docker &>/dev/null; then
    success "Docker já instalado: $(docker --version)"
else
    info "A instalar Docker..."
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker "${INSTALL_USER}"
    success "Docker instalado. NOTA: Faz logout/login para o grupo docker funcionar."
fi

# ═══════════════════════════════════════════════════════════════════
# 3. TAILSCALE (opcional)
# ═══════════════════════════════════════════════════════════════════
if command -v tailscale &>/dev/null; then
    success "Tailscale já instalado"
else
    read -p "Instalar Tailscale? (y/N) " -r
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        curl -fsSL https://tailscale.com/install.sh | sh
        sudo tailscale up
        success "Tailscale instalado"
    else
        warn "Tailscale não instalado"
    fi
fi

# ═══════════════════════════════════════════════════════════════════
# 4. CLONAR REPOSITÓRIO
# ═══════════════════════════════════════════════════════════════════
if [ -d "${PROJECT_DIR}" ]; then
    warn "Projecto já existe em ${PROJECT_DIR}"
    read -p "Fazer pull das últimas alterações? (y/N) " -r
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cd "${PROJECT_DIR}" && git pull
    fi
else
    info "A clonar repositório..."
    git clone https://github.com/blankV0/password-manager.git "${PROJECT_DIR}"
    success "Repositório clonado"
fi

cd "${PROJECT_DIR}"

# ═══════════════════════════════════════════════════════════════════
# 5. CONFIGURAR .ENV
# ═══════════════════════════════════════════════════════════════════
if [ -f "${PROJECT_DIR}/.env" ]; then
    success ".env já existe"
else
    warn "Ficheiro .env não encontrado!"
    echo ""
    echo "Opções:"
    echo "  1) Copiar de outro servidor (recomendado)"
    echo "  2) Gerar novo a partir do template"
    echo ""
    read -p "Opção (1/2): " -r ENV_OPTION

    case ${ENV_OPTION} in
        1)
            echo "Copia o .env para: ${PROJECT_DIR}/.env"
            echo "Depois corre este script novamente."
            exit 0
            ;;
        2)
            cp .env.example .env
            # Gerar JWT secret
            JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")
            sed -i "s|AUTH_JWT_SECRET=<CHANGE_ME>|AUTH_JWT_SECRET=${JWT_SECRET}|" .env
            warn "Ficheiro .env criado com secret gerado."
            warn "Revisa o .env antes de continuar!"
            echo ""
            read -p "Já revisaste o .env? (y/N) " -r
            [[ $REPLY =~ ^[Yy]$ ]] || exit 0
            ;;
    esac
fi

chmod 600 .env

# ═══════════════════════════════════════════════════════════════════
# 6. CERTIFICADOS TLS
# ═══════════════════════════════════════════════════════════════════
CERT_DIR="${PROJECT_DIR}/nginx/certs"
mkdir -p "${CERT_DIR}"

if [ -f "${CERT_DIR}/fullchain.pem" ]; then
    success "Certificado TLS já existe"
else
    warn "Certificado TLS não encontrado!"
    echo ""
    echo "Opções:"
    echo "  1) Gerar self-signed (para teste/home server)"
    echo "  2) Copiar certs existentes manualmente"
    echo ""
    read -p "Opção (1/2): " -r CERT_OPTION

    case ${CERT_OPTION} in
        1)
            info "A gerar certificado self-signed..."
            openssl req -x509 -nodes -days 365 -newkey rsa:4096 \
                -keyout "${CERT_DIR}/privkey.pem" \
                -out "${CERT_DIR}/fullchain.pem" \
                -subj "/CN=localhost"
            chmod 600 "${CERT_DIR}/privkey.pem"
            success "Certificado self-signed gerado (365 dias)"
            ;;
        2)
            echo "Copia os certs para: ${CERT_DIR}/"
            echo "  fullchain.pem (certificado)"
            echo "  privkey.pem   (chave privada)"
            exit 0
            ;;
    esac
fi

# ═══════════════════════════════════════════════════════════════════
# 7. RESTAURAR BACKUP (opcional)
# ═══════════════════════════════════════════════════════════════════
echo ""
read -p "Restaurar backup da base de dados? (y/N) " -r
if [[ $REPLY =~ ^[Yy]$ ]]; then
    read -p "Caminho do backup (.db.gz): " -r BACKUP_PATH
    if [ -f "${BACKUP_PATH}" ]; then
        mkdir -p "${BACKUP_DIR}"
        cp "${BACKUP_PATH}" "${BACKUP_DIR}/"
        info "Backup copiado. Será restaurado após o deploy."
    else
        warn "Ficheiro não encontrado: ${BACKUP_PATH}"
    fi
fi

# ═══════════════════════════════════════════════════════════════════
# 8. BUILD E DEPLOY
# ═══════════════════════════════════════════════════════════════════
info "A fazer build e deploy..."
docker compose build 2>&1 | tail -5
docker compose up -d 2>&1
success "Containers iniciados"

# Esperar pelo health check
info "A esperar que o serviço fique healthy..."
RETRIES=0
while [ ${RETRIES} -lt 30 ]; do
    HEALTH=$(docker inspect pm_auth --format '{{.State.Health.Status}}' 2>/dev/null || echo "starting")
    if [ "${HEALTH}" = "healthy" ]; then
        success "Serviço healthy!"
        break
    fi
    RETRIES=$((RETRIES + 1))
    sleep 2
done

if [ "${HEALTH}" != "healthy" ]; then
    warn "Serviço pode não estar healthy. Verifica: docker compose logs"
fi

# ═══════════════════════════════════════════════════════════════════
# 9. SSH HARDENING
# ═══════════════════════════════════════════════════════════════════
info "A configurar SSH hardening..."
if [ -f "${PROJECT_DIR}/scripts/harden_server.sh" ]; then
    sudo bash "${PROJECT_DIR}/scripts/harden_server.sh" 2>&1 | tail -5
    # Corrigir prioridade (antes do cloud-init)
    if [ -f /etc/ssh/sshd_config.d/hardening.conf ]; then
        sudo mv /etc/ssh/sshd_config.d/hardening.conf /etc/ssh/sshd_config.d/01-hardening.conf 2>/dev/null || true
    fi
    sudo systemctl reload ssh 2>/dev/null || sudo systemctl reload sshd 2>/dev/null || true
    success "SSH hardening aplicado"
fi

# ═══════════════════════════════════════════════════════════════════
# 10. UFW FIREWALL
# ═══════════════════════════════════════════════════════════════════
info "A configurar firewall..."
sudo ufw default deny incoming 2>/dev/null || true
sudo ufw default allow outgoing 2>/dev/null || true
sudo ufw allow 22/tcp 2>/dev/null || true
sudo ufw allow 80/tcp 2>/dev/null || true
sudo ufw allow 443/tcp 2>/dev/null || true
echo "y" | sudo ufw enable 2>/dev/null || true
success "Firewall configurado (22, 80, 443)"

# ═══════════════════════════════════════════════════════════════════
# 11. CRON JOBS
# ═══════════════════════════════════════════════════════════════════
info "A configurar cron jobs..."
mkdir -p "${BACKUP_DIR}"
chmod 700 "${BACKUP_DIR}"

# Remover crons antigos do PM
crontab -l 2>/dev/null | grep -v "password-manager" | crontab - 2>/dev/null || true

# Adicionar crons
(crontab -l 2>/dev/null || true; cat <<CRON
# Password Manager — Backup DB (cada 6h)
0 */6 * * * ${PROJECT_DIR}/scripts/backup_db.sh >> ${PROJECT_DIR}/logs/backup.log 2>&1
# Password Manager — Health monitor (cada 5 min)
*/5 * * * * ${PROJECT_DIR}/scripts/health_monitor.sh 2>&1
# Password Manager — Offsite backup (30min após backup local)
30 */6 * * * ${PROJECT_DIR}/scripts/backup_offsite.sh >> ${PROJECT_DIR}/logs/backup_offsite.log 2>&1
CRON
) | crontab -

success "Cron jobs configurados"

# ═══════════════════════════════════════════════════════════════════
# 12. PERMISSÕES
# ═══════════════════════════════════════════════════════════════════
chmod 600 "${PROJECT_DIR}/.env"
chmod 600 "${CERT_DIR}/privkey.pem" 2>/dev/null || true
chmod 750 "${PROJECT_DIR}/scripts/"*.sh
chmod 700 "${BACKUP_DIR}"

success "Permissões configuradas"

# ═══════════════════════════════════════════════════════════════════
# RESUMO
# ═══════════════════════════════════════════════════════════════════
echo ""
echo "═══════════════════════════════════════════════════════════"
echo -e "  ${GREEN}✅ Bootstrap concluído!${NC}"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "  Status:    docker compose ps"
echo "  Logs:      docker compose logs -f"
echo "  Health:    curl -sk https://localhost/health"
echo "  Backups:   ls -la ${BACKUP_DIR}/"
echo ""
echo "  Próximos passos:"
echo "  1. Verificar acesso SSH por chave funciona"
echo "  2. Configurar GitHub Deploy Key (ver DISASTER_RECOVERY.md)"
echo "  3. Configurar alerts: ${PROJECT_DIR}/scripts/alerts.sh"
echo "  4. Testar backup: bash ${PROJECT_DIR}/scripts/backup_db.sh"
echo ""

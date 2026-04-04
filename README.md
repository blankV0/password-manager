# 🔐 Password Manager

> Sistema de autenticação seguro com cliente desktop — projeto académico com engenharia de nível profissional.

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://docs.docker.com/compose/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.0.0-brightgreen.svg)](VERSION)

---

## 📋 Índice

- [Arquitetura](#-arquitetura)
- [Funcionalidades](#-funcionalidades)
- [Início Rápido](#-início-rápido)
- [Configuração](#-configuração)
- [Deploy em Produção](#-deploy-em-produção)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [Variáveis de Ambiente](#-variáveis-de-ambiente)
- [Endpoints da API](#-endpoints-da-api)
- [Decisões de Segurança](#-decisões-de-segurança)
- [Destaques Técnicos](#-destaques-técnicos)
- [Licença](#-licença)

---

## 🏗 Arquitetura

```
┌─────────────────────────────────────────────────────────┐
│                    CLIENTE DESKTOP                       │
│  ┌──────────┐  ┌──────────┐  ┌────────────────────┐    │
│  │ Login UI │  │ Register │  │ Dashboard + Sidebar │    │
│  │ (Tkinter)│  │   UI     │  │  ┌──────────────┐  │    │
│  └────┬─────┘  └────┬─────┘  │  │  gerador1/   │  │    │
│       │              │        │  │  (gerador,   │  │    │
│       └──────┬───────┘        │  │  gestor,     │  │    │
│              ▼                │  │  verificador)│  │    │
│  ┌───────────────────────┐   │  └──────────────┘  │    │
│  │   local_auth.py       │   │  ┌──────────────┐  │    │
│  │   (HTTP auth client)  │   │  │  Vault GUI   │  │    │
│  └───────────┬───────────┘   │  │  (AES-256)   │  │    │
│              │               │  └──────────────┘  │    │
│              │               └────────────────────┘    │
└──────────────┼──────────────────────────────────────────┘
               │ HTTPS (Tailscale VPN)
               ▼
┌──────────────────────────────────────────────────────────┐
│                 SERVIDOR DE PRODUÇÃO                      │
│                                                          │
│  ┌────────────────────┐      ┌────────────────────────┐  │
│  │   Nginx (TLS)      │      │   FastAPI / Uvicorn    │  │
│  │   ├ Rate limiting  │─────▶│   ├ /auth/register     │  │
│  │   ├ Security hdrs  │      │   ├ /auth/login        │  │
│  │   ├ HTTPS redirect │      │   ├ /auth/refresh      │  │
│  │   └ /docs blocked  │      │   ├ /auth/logout       │  │
│  │     (production)   │      │   ├ /auth/me           │  │
│  └────────────────────┘      │   ├ /auth/change-pw    │  │
│                              │   ├ /admin/*           │  │
│                              │   └ /health            │  │
│                              └───────────┬────────────┘  │
│                                          │               │
│                              ┌───────────▼────────────┐  │
│                              │   SQLite (WAL mode)    │  │
│                              │   ├ users              │  │
│                              │   ├ refresh_tokens     │  │
│                              │   └ auth_events        │  │
│                              └────────────────────────┘  │
│                                                          │
│  Docker Compose: non-root, read-only fs, no-new-privs   │
└──────────────────────────────────────────────────────────┘
```

---

## ✨ Funcionalidades

### 🔒 Segurança

| Feature | Detalhe |
|---------|---------|
| Password hashing | **Argon2id** (OWASP recommended, time_cost=3, 64 MiB) |
| Access tokens | **JWT HS256**, TTL 15 min, claims mínimos |
| Refresh tokens | Opacos, apenas SHA-256 hash guardado na DB |
| Token rotation | Rotação automática com deteção de reutilização |
| Account lockout | 5 tentativas falhadas → bloqueio 15 min |
| Rate limiting | Sliding-window (app-level) + Nginx (network-level) |
| Security gate | Recusa iniciar em produção com JWT secret fraco |
| API docs | Bloqueados em produção (`/docs`, `/redoc`, `/openapi.json`) |
| Audit trail | Todos os eventos auth registados na DB + ficheiros de log |

### 🖥 Cliente Desktop

| Feature | Detalhe |
|---------|---------|
| Interface | **Tkinter** com dark/light theme e título personalizado (Win32) |
| Gerador | Gerador de passwords com políticas configuráveis |
| Gestor | Gestor de passwords com vault encriptado |
| Verificador | Verificador de força de password em tempo real |
| Vault | Encriptação **AES-256-GCM** — arquitetura KEK/DEK, Argon2id KDF |
| Auth client | Retry logic, token refresh automático, gestão segura de credenciais |
| Painel admin | Gestão de utilizadores (admin only) |
| Definições | Página de settings com preferências persistentes |

### 🐳 Infraestrutura

| Feature | Detalhe |
|---------|---------|
| Containers | **Docker Compose** — non-root, read-only fs, no-new-privileges |
| Proxy | **Nginx** — TLS termination, HSTS, CSP, X-Frame-Options |
| Deploy | Deploy atómico com rollback instantâneo |
| Monitorização | Health checks automáticos com alertas Discord/Telegram |
| Backups | Automáticos (local + offsite) com scripts de restore |
| Firewall | UFW + Docker iptables hardening |
| Disaster recovery | Script de bootstrap para reconstrução total do servidor |

---

## 🚀 Início Rápido

### Pré-requisitos

- **Python 3.11+**
- **pip**
- **Tailscale** (para ligação ao servidor de produção)

### 1. Clonar e instalar

```bash
git clone https://github.com/<username>/password-manager.git
cd password-manager

python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configurar

```bash
cp .env.example .env
```

Editar `.env` e preencher:

```dotenv
API_BASE_URL=https://<IP_TAILSCALE_DO_SERVIDOR>
```

> **Nota:** Obter o IP Tailscale do servidor com `tailscale ip -4`

### 3. Executar

```bash
python main.py
```

---

## ⚙ Configuração

Toda a configuração é feita via variáveis de ambiente no ficheiro `.env`.
O template `.env.example` documenta cada variável.

```bash
# Copiar o template
cp .env.example .env

# Editar com o teu editor preferido
code .env    # ou: nano .env
```

> ⚠️ **Nunca commitar o `.env` real** — já está no `.gitignore`.

---

## 🐳 Deploy em Produção

> **Target:** Ubuntu Server + Docker + Nginx + TLS via Tailscale

### 1. Instalar Docker

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER && newgrp docker
```

### 2. Configurar secrets

```bash
cp .env.example .env
python docker/deploy/generate_secrets.py
# Colar o AUTH_JWT_SECRET gerado no .env
# Definir APP_ENV=production
```

### 3. Certificado TLS

Colocar os certificados em:

- `docker/nginx/certs/fullchain.pem`
- `docker/nginx/certs/privkey.pem`

Ver [docker/nginx/certs/README.txt](docker/nginx/certs/README.txt) para instruções Tailscale / Let's Encrypt / self-signed.

### 4. Firewall

```bash
sudo ./docker/deploy/ufw_setup.sh
sudo systemctl restart docker
```

### 5. Deploy

```bash
cd docker
docker compose build && docker compose up -d
```

### 6. Validar

```bash
./docker/deploy/healthcheck.sh --host https://<hostname>
```

Esperado: health OK, HTTPS ativo, security headers presentes, `/docs` bloqueado.

---

## 📁 Estrutura do Projeto

```
password-manager/
│
├── main.py                         # Entry point — app desktop (Tkinter)
├── auth_server.py                  # Entry point — FastAPI auth server
├── requirements.txt                # Dependências Python (desktop)
├── .env.example                    # Template de variáveis de ambiente
├── .gitignore                      # Regras git ignore
├── .dockerignore                   # Regras Docker ignore
├── VERSION                         # Versão semântica (1.0.0)
├── CHANGELOG.md                    # Histórico de alterações
├── README.md                       # Este ficheiro
│
├── src/                            # ── Código-fonte principal ──
│   ├── __init__.py                 #    __version__ = "1.0.0"
│   │
│   ├── auth/                       #    Módulo de autenticação (backend)
│   │   ├── api.py                  #      Route handlers REST
│   │   ├── service.py              #      Lógica de negócio (register/login/refresh/logout)
│   │   ├── database.py             #      Schema SQLite, migrações, cleanup
│   │   ├── schemas.py              #      Modelos Pydantic (request/response)
│   │   ├── tokens.py               #      Criação/decode JWT, hash de refresh tokens
│   │   ├── passwords.py            #      Argon2id hash/verify/rehash
│   │   ├── config.py               #      Settings baseados em .env (frozen dataclass)
│   │   ├── dependencies.py         #      Wiring DI FastAPI (singleton service, auth guard)
│   │   └── rate_limiter.py         #      Sliding-window limiter (thread-safe)
│   │
│   ├── config/                     #    Configuração partilhada
│   │   └── settings.py             #      Settings centralizados (API, email, SMS, UI)
│   │
│   ├── core/                       #    Camada criptográfica (AES-256-GCM)
│   │   ├── crypto.py               #      CryptoProvider (KEK/DEK, wrap/unwrap, encrypt/decrypt)
│   │   ├── encryption.py           #      Primitivas AES-256-GCM
│   │   ├── key_derivation.py       #      Argon2id key derivation (t=3, m=64 MiB)
│   │   └── secure_memory.py        #      secure_zero() + SecureBytes RAII
│   │
│   ├── models/                     #    Modelos de dados
│   │   └── local_auth.py           #      Cliente HTTP para a API auth (lado desktop)
│   │
│   ├── services/                   #    Serviços opcionais
│   │   ├── email_verification.py   #      Fluxos de verificação email + SMTP
│   │   └── sms_verification.py     #      Verificação SMS (Twilio / dev mode)
│   │
│   ├── storage/                    #    Persistência encriptada do vault (preparado)
│   │
│   ├── ui/                         #    Interface gráfica desktop
│   │   ├── login_gui.py            #      Ecrãs de login, registo, dashboard
│   │   ├── vault_gui.py            #      Janela do vault de passwords
│   │   ├── vault_entry_dialog.py   #      Diálogo CRUD de entradas do vault
│   │   ├── password_strength.py    #      Widget indicador de força
│   │   ├── settings_page.py        #      Página de definições (tema, timeouts)
│   │   └── admin_panel.py          #      Painel de administração (gestão de users)
│   │
│   └── utils/                      #    Utilitários
│       ├── logging_config.py       #      Setup de logging estruturado
│       └── security_validator.py   #      Validação de input + masking de email
│
├── gerador1/                       # ── Módulo gerador/gestor de passwords ──
│   ├── inicio.py                   #    Menu principal do módulo
│   ├── gerador.py                  #    Gerador de passwords configurável
│   ├── gerenciador.py              #    Gestor de passwords guardadas
│   ├── verificador.py              #    Verificador de força de password
│   ├── politicas.py                #    Políticas de password configuráveis
│   └── utilizador.py               #    Gestão de perfil de utilizador
│
├── certs/                          # ── Certificados (desktop) ──
│   └── server_ca.pem.localhost_only #   CA cert para verificação TLS local
│
├── data/                           # ── Dados persistentes ──
│   └── preferences.json            #    Preferências UI (tema, timeouts)
│
├── logs/                           # ── Logs da aplicação (gitignored) ──
│   └── .gitkeep
│
└── docker/                         # ── Infraestrutura Docker ──
    ├── Dockerfile                  #    Multi-stage build, non-root, healthcheck
    ├── docker-compose.yml          #    Orquestração: auth + nginx
    ├── requirements.server.txt     #    Dependências Python (servidor)
    │
    ├── nginx/                      #    Reverse proxy
    │   ├── nginx.conf              #      Config global (rate limit zones, timeouts)
    │   ├── conf.d/
    │   │   ├── auth.conf           #      TLS, security headers, proxy rules
    │   │   └── proxy_params.conf   #      Parâmetros de proxy partilhados
    │   └── certs/
    │       └── README.txt          #      Instruções para certificados TLS
    │
    ├── scripts/                    #    Scripts operacionais
    │   ├── deploy.sh               #      Deploy atómico com backup pré-deploy
    │   ├── rollback.sh             #      Rollback instantâneo
    │   ├── backup_db.sh            #      Backup local da base de dados
    │   ├── backup_offsite.sh       #      Backup offsite
    │   ├── restore_db.sh           #      Restauro de base de dados
    │   ├── bootstrap.sh            #      Disaster recovery (rebuild completo)
    │   ├── health_monitor.sh       #      Monitorização contínua de saúde
    │   ├── alerts.sh               #      Notificações Discord/Telegram
    │   └── harden_server.sh        #      Hardening SSH
    │
    └── deploy/                     #    Utilidades de deploy
        ├── generate_secrets.py     #      Gerador de secrets criptográficos
        ├── healthcheck.sh          #      Suite de validação pós-deploy
        └── ufw_setup.sh            #      Baseline de firewall UFW
```

---

## 🔧 Variáveis de Ambiente

### Cliente Desktop

| Variável | Default | Descrição |
|----------|---------|-----------|
| `API_BASE_URL` | `https://localhost:8000` | URL do servidor de autenticação |
| `API_TIMEOUT` | `10` | Timeout de requests (segundos) |

### Servidor de Autenticação

| Variável | Default | Descrição |
|----------|---------|-----------|
| `APP_ENV` | `development` | `development` ou `production` |
| `AUTH_JWT_SECRET` | *(obrigatório em prod)* | Secret para assinatura JWT |
| `AUTH_DB_PATH` | `data/auth.db` | Caminho da base de dados SQLite |
| `AUTH_ACCESS_TOKEN_TTL_SECONDS` | `900` | Tempo de vida do access token (15 min) |
| `AUTH_REFRESH_TOKEN_TTL_SECONDS` | `604800` | Tempo de vida do refresh token (7 dias) |
| `AUTH_LOGIN_MAX_FAILURES` | `5` | Tentativas antes de bloqueio |
| `AUTH_LOGIN_LOCKOUT_SECONDS` | `900` | Duração do bloqueio (15 min) |
| `AUTH_RATE_LIMIT_MAX_ATTEMPTS` | `10` | Threshold do rate limiter |
| `AUTH_PASSWORD_MIN_LENGTH` | `12` | Comprimento mínimo de password |

---

## 🌐 Endpoints da API

| Método | Path | Auth | Descrição |
|--------|------|------|-----------|
| `POST` | `/auth/register` | — | Criar conta |
| `POST` | `/auth/login` | — | Login → JWT + refresh token |
| `POST` | `/auth/refresh` | — | Rodar refresh token |
| `POST` | `/auth/logout` | — | Revogar refresh token |
| `GET` | `/auth/me` | Bearer | Perfil do utilizador atual |
| `POST` | `/auth/change-password` | Bearer | Alterar password |
| `GET` | `/admin/users` | Bearer (admin) | Listar utilizadores |
| `PUT` | `/admin/users/{id}/role` | Bearer (admin) | Alterar role |
| `DELETE` | `/admin/users/{id}` | Bearer (admin) | Eliminar utilizador |
| `GET` | `/health` | — | Health check |

---

## 🛡 Decisões de Segurança

| Decisão | Porquê |
|---------|--------|
| Argon2id (não bcrypt) | Vencedor do PHC, resistente a GPU/ASIC, recomendado OWASP |
| JWT + refresh opaco | Access curto (15 min) + refresh rotativo longo (7 dias) |
| SHA-256 nos refresh tokens | Leak da DB não compromete sessões |
| Deteção de reutilização | Token roubado → revoga toda a família |
| Constant-time em login falhado | Sleep 350ms previne enumeração de users por timing |
| Security gate no startup | Bloqueia produção com JWT secret fraco/default |
| Docker non-root + read-only fs | Limita blast radius de comprometimento do container |
| Rate limiting duplo | Defesa em profundidade: rede (Nginx) + aplicação (FastAPI) |

---

## 🏆 Destaques Técnicos

Este projeto demonstra práticas reais de **DevSecOps** num contexto académico:

1. **Defesa em profundidade** — segurança em cada camada (rede, proxy, aplicação, base de dados)
2. **Modelo zero-trust de tokens** — rotação de refresh com deteção de reutilização, JWT com claims mínimos
3. **Infraestrutura production-grade** — Docker, Nginx, deploy atómico, rollback automático
4. **Maturidade operacional** — monitorização, alertas, backup/restore, disaster recovery
5. **Arquitetura limpa** — separação de concerns (API → Service → Database), DI, frozen config
6. **Criptografia moderna** — AES-256-GCM com arquitetura KEK/DEK, Argon2id KDF, secure memory wiping

---

## 📄 Licença

Projeto académico — MIT License.

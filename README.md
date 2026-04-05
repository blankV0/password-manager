# 🔐 Password Manager

> Gestor de passwords seguro com cliente desktop e servidor de autenticação — projeto académico com engenharia de nível profissional.

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://docs.docker.com/compose/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.0.0-brightgreen.svg)](VERSION)

---

## 📋 Índice

- [Visão Geral](#-visão-geral)
- [Arquitetura](#-arquitetura)
- [Funcionalidades](#-funcionalidades)
- [Screenshots](#-screenshots)
- [Início Rápido](#-início-rápido)
- [Configuração](#-configuração)
- [Deploy em Produção](#-deploy-em-produção)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [Variáveis de Ambiente](#-variáveis-de-ambiente)
- [Endpoints da API](#-endpoints-da-api)
- [Decisões de Segurança](#-decisões-de-segurança)
- [Stack Tecnológico](#-stack-tecnológico)
- [Licença](#-licença)

---

## 🎯 Visão Geral

Password Manager é uma aplicação desktop (Tkinter) com servidor de autenticação (FastAPI) que permite:

- **Registar e autenticar** utilizadores com passwords seguras (Argon2id)
- **Gerar passwords** aleatórias com políticas configuráveis
- **Guardar credenciais** num gerenciador encriptado (AES-256-GCM, zero-knowledge)
- **Verificar a força** de passwords em tempo real
- **Gerir utilizadores** via painel de administração
- **Verificar emails** através de fluxo SMTP com token temporário

A comunicação entre o cliente e o servidor é feita via HTTPS sobre VPN Tailscale, com TLS terminado no Nginx.

---

## 🏗 Arquitetura

```
┌──────────────────────────────────────────────────────────────┐
│                      CLIENTE DESKTOP (Tkinter)               │
│                                                              │
│  ┌────────────┐  ┌────────────┐  ┌─────────────────────┐    │
│  │  Login /   │  │ Dashboard  │  │     Sidebar         │    │
│  │  Registo   │  │  (inicio)  │  │  ┌───────────────┐  │    │
│  │  ────────  │  │  ────────  │  │  │ 🏠 Início     │  │    │
│  │  Email     │  │  Stats     │  │  │ 🔐 Gerenciador│  │    │
│  │  Password  │  │  Quick     │  │  │ 🔑 Gerador    │  │    │
│  │  Username  │  │  Actions   │  │  │ 🛡 Verificador│  │    │
│  └─────┬──────┘  └────────────┘  │  │ 👤 Utilizador │  │    │
│        │                         │  │ ⚙️ Definições  │  │    │
│        │  ┌──────────────────┐   │  │ 🔧 Admin      │  │    │
│        │  │   Gerenciador    │   │  └───────────────┘  │    │
│        │  │   (Vault GUI)    │   └─────────────────────┘    │
│        │  │  ┌────────────┐  │                              │
│        │  │  │ AES-256-GCM│  │  Encriptação client-side:    │
│        │  │  │ KEK / DEK  │  │  Servidor NUNCA vê plaintext │
│        │  │  │ Argon2id   │  │                              │
│        │  │  └────────────┘  │                              │
│        │  └──────────────────┘                              │
│        │                                                    │
│  ┌─────▼──────────────────────────────┐                     │
│  │  local_auth.py (HTTP auth client)  │                     │
│  │  ├ login / register / refresh      │                     │
│  │  ├ check_email_verified            │                     │
│  │  ├ vault CRUD (ciphertext only)    │                     │
│  │  └ admin operations                │                     │
│  └──────────────┬─────────────────────┘                     │
└─────────────────┼───────────────────────────────────────────┘
                  │
                  │ HTTPS (TLS 1.2/1.3 via Tailscale VPN)
                  ▼
┌──────────────────────────────────────────────────────────────┐
│                  SERVIDOR DE PRODUÇÃO (Docker)               │
│                                                              │
│  ┌────────────────────────┐    ┌───────────────────────────┐ │
│  │      Nginx (Alpine)    │    │   FastAPI + Uvicorn       │ │
│  │  ┌──────────────────┐  │    │                           │ │
│  │  │ TLS termination  │  │    │   AUTH ENDPOINTS          │ │
│  │  │ Rate limiting    │──┼───▶│   POST /auth/register     │ │
│  │  │ Security headers │  │    │   POST /auth/login        │ │
│  │  │ HSTS / CSP       │  │    │   POST /auth/refresh      │ │
│  │  │ /docs bloqueado  │  │    │   POST /auth/logout       │ │
│  │  └──────────────────┘  │    │   GET  /auth/me           │ │
│  └────────────────────────┘    │   POST /auth/change-pw    │ │
│                                │                           │ │
│                                │   VERIFICATION            │ │
│                                │   GET  /auth/verify-email │ │
│                                │   POST /auth/resend-verif │ │
│                                │   GET  /auth/check-verif  │ │
│                                │                           │ │
│                                │   VAULT (zero-knowledge)  │ │
│                                │   POST /vault/key         │ │
│                                │   GET  /vault/key         │ │
│                                │   PUT  /vault/key         │ │
│                                │   GET  /vault/entries     │ │
│                                │   POST /vault/entries     │ │
│                                │   PUT  /vault/entries/:id │ │
│                                │   DEL  /vault/entries/:id │ │
│                                │                           │ │
│                                │   ADMIN (role=admin)      │ │
│                                │   POST /admin/users       │ │
│                                │   POST /admin/user/active │ │
│                                │   POST /admin/user/reset  │ │
│                                │   POST /admin/user/delete │ │
│                                │   POST /admin/logs        │ │
│                                │   DEL  /account/delete    │ │
│                                └──────────┬────────────────┘ │
│                                           │                  │
│                                ┌──────────▼────────────────┐ │
│                                │   SQLite (WAL mode)       │ │
│                                │   ├ users                 │ │
│                                │   ├ refresh_tokens        │ │
│                                │   ├ auth_events           │ │
│                                │   ├ email_verifications   │ │
│                                │   ├ vault_keys            │ │
│                                │   └ vault_entries         │ │
│                                └───────────────────────────┘ │
│                                                              │
│  Segurança: non-root, read-only fs, no-new-privileges       │
│  Rede: container auth isolado, só nginx acede (pm_internal)  │
└──────────────────────────────────────────────────────────────┘
```

---

## ✨ Funcionalidades

### 🔒 Segurança & Autenticação

| Feature | Detalhe |
|---------|---------|
| Password hashing | **Argon2id** (OWASP recommended, time_cost=3, 64 MiB) |
| Access tokens | **JWT HS256**, TTL 15 min, claims mínimos |
| Refresh tokens | Opacos, apenas SHA-256 hash guardado na DB |
| Token rotation | Rotação automática com deteção de reutilização |
| Account lockout | 5 tentativas falhadas → bloqueio 15 min |
| Rate limiting | Sliding-window (app-level) + Nginx (network-level) |
| SQL Injection | **Imune** — 100% parameterized queries (`?` placeholders) |
| Input validation | **Pydantic** schemas com `EmailStr`, `Field(min_length, max_length)` |
| Security gate | Recusa iniciar em produção com JWT secret fraco |
| API docs | Bloqueados em produção (`/docs`, `/redoc`, `/openapi.json`) |
| Audit trail | Todos os eventos auth registados na DB + ficheiros de log |
| Verificação email | Fluxo SMTP com token temporário (24h TTL) |

### 🔐 Gerenciador de Passwords (Vault)

| Feature | Detalhe |
|---------|---------|
| Encriptação | **AES-256-GCM** — nível militar, authenticated encryption |
| Arquitetura | **KEK/DEK** — Master password → Argon2id → KEK → unwrap DEK |
| Zero-knowledge | Servidor guarda **apenas ciphertext** — nunca vê passwords em claro |
| CRUD completo | Criar, ler, editar e apagar credenciais encriptadas |
| Exportação | Exportar vault como ficheiro JSON encriptado |
| Guardar do gerador | Botão direto no gerador para guardar password no gerenciador |

### 🖥 Cliente Desktop

| Feature | Detalhe |
|---------|---------|
| Interface | **Tkinter** com dark/light theme e sidebar de navegação |
| Página Início | Dashboard com stats do vault e ações rápidas |
| Gerador | Gerador de passwords com tamanho, letras, números, símbolos |
| Verificador | Verificador de força de password em tempo real |
| Utilizador | Perfil com estatísticas, exportação e eliminação de dados |
| Definições | Página de settings com tema, timeouts e zona de perigo |
| Painel Admin | Gestão de utilizadores: ativar/desativar, reset password, eliminar |
| Auto-delete | Utilizador pode eliminar a sua própria conta |

### 🐳 Infraestrutura

| Feature | Detalhe |
|---------|---------|
| Containers | **Docker Compose** — non-root, read-only fs, no-new-privileges |
| Proxy | **Nginx** — TLS 1.2/1.3, HSTS, CSP, X-Frame-Options |
| Rede | Container auth **isolado** — só nginx comunica (rede interna) |
| Deploy | Deploy atómico com backup pré-deploy e rollback instantâneo |
| Monitorização | Health checks automáticos com alertas Discord/Telegram |
| Backups | SQLite backup cada 6h + offsite + scripts de restore |
| Firewall | UFW (deny default, allow 22/80/443) + Docker iptables |
| SSH hardening | Password auth disabled, MaxAuthTries 3, fail2ban |
| Disaster recovery | Script de bootstrap para reconstrução total do servidor |

---

## 📸 Screenshots

> *Em construção — adicionar screenshots da app aqui.*

---

## 🚀 Início Rápido

### Pré-requisitos

- **Python 3.11+**
- **pip**
- **Tailscale** (para ligação ao servidor de produção)

### 1. Clonar e instalar

```bash
git clone https://github.com/blankV0/password-manager.git
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

A app abre a janela de login. Depois de autenticar, acedes ao dashboard com todas as funcionalidades.

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
python deploy/generate_secrets.py
# Colar o AUTH_JWT_SECRET gerado no .env
# Definir APP_ENV=production
```

### 3. Certificado TLS

Colocar os certificados em:

- `nginx/certs/fullchain.pem`
- `nginx/certs/privkey.pem`

> Suporta: Tailscale cert, Let's Encrypt ou self-signed.

### 4. Firewall

```bash
sudo ./deploy/ufw_setup.sh
sudo systemctl restart docker
```

### 5. Deploy

```bash
docker compose build && docker compose up -d
```

### 6. Validar

```bash
./deploy/healthcheck.sh --host https://<hostname>
```

Esperado: health OK, HTTPS ativo, security headers presentes, `/docs` bloqueado.

---

## 📁 Estrutura do Projeto

```
password-manager/
│
├── main.py                          # Entry point — app desktop (Tkinter)
├── auth_server.py                   # Entry point — FastAPI auth server
├── requirements.txt                 # Dependências Python (desktop)
├── requirements.server.txt          # Dependências Python (servidor Docker)
├── docker-compose.yml               # Orquestração Docker (auth + nginx)
├── Dockerfile                       # Multi-stage build, non-root, healthcheck
├── .env.example                     # Template de variáveis de ambiente
├── .gitignore                       # Regras git ignore
├── .dockerignore                    # Regras Docker ignore
├── VERSION                          # Versão semântica (1.0.0)
├── CHANGELOG.md                     # Histórico de alterações
├── README.md                        # Este ficheiro
│
├── src/                             # ── Código-fonte principal ──
│   ├── __init__.py
│   │
│   ├── auth/                        #    Módulo de autenticação (servidor)
│   │   ├── api.py                   #      Endpoints REST (register, login, verify, admin)
│   │   ├── service.py               #      Lógica de negócio (AuthService)
│   │   ├── database.py              #      Schema SQLite, migrações, cleanup
│   │   ├── schemas.py               #      Modelos Pydantic (request/response)
│   │   ├── tokens.py                #      Criação/decode JWT, hash de refresh tokens
│   │   ├── passwords.py             #      Argon2id hash/verify/rehash
│   │   ├── config.py                #      Settings do servidor (frozen dataclass)
│   │   ├── dependencies.py          #      Wiring DI FastAPI (singleton, auth guard)
│   │   ├── rate_limiter.py          #      Sliding-window limiter (thread-safe)
│   │   ├── email_service.py         #      Envio de emails SMTP (verificação)
│   │   ├── vault_api.py             #      Endpoints REST do vault (zero-knowledge)
│   │   └── vault_schemas.py         #      Modelos Pydantic do vault
│   │
│   ├── config/                      #    Configuração partilhada (desktop)
│   │   └── settings.py              #      Settings centralizados (API, email, SMS, UI)
│   │
│   ├── core/                        #    Camada criptográfica
│   │   ├── crypto.py                #      CryptoProvider (KEK/DEK, wrap/unwrap, encrypt/decrypt)
│   │   ├── encryption.py            #      Primitivas AES-256-GCM
│   │   ├── key_derivation.py        #      Argon2id key derivation (t=3, m=64 MiB)
│   │   └── secure_memory.py         #      secure_zero() + SecureBytes RAII
│   │
│   ├── models/                      #    Modelos de dados (desktop)
│   │   └── local_auth.py            #      Cliente HTTP para a API auth
│   │
│   ├── services/                    #    Serviços auxiliares (desktop)
│   │   ├── email_verification.py    #      Fluxo de verificação de email
│   │   └── sms_verification.py      #      Verificação SMS (Twilio / dev mode)
│   │
│   ├── storage/                     #    Persistência encriptada do vault
│   │   └── vault_crypto.py          #      Operações criptográficas do vault
│   │
│   ├── ui/                          #    Interface gráfica desktop (Tkinter)
│   │   ├── login_gui.py             #      Ecrãs de login, registo, verificação email
│   │   ├── vault_gui.py             #      Gerenciador de passwords (VaultPage)
│   │   ├── vault_entry_dialog.py    #      Diálogo CRUD de entradas
│   │   ├── password_strength.py     #      Widget indicador de força
│   │   ├── settings_page.py         #      Página de definições (tema, zona de perigo)
│   │   └── admin_panel.py           #      Painel de administração (gestão de users)
│   │
│   └── utils/                       #    Utilitários
│       ├── logging_config.py        #      Setup de logging estruturado
│       └── security_validator.py    #      Validação de input + masking de email/phone
│
├── gerador1/                        # ── Módulo gerador/gestor de passwords ──
│   ├── inicio.py                    #    Página inicial (dashboard com stats)
│   ├── gerador.py                   #    Gerador de passwords configurável
│   ├── gerenciador.py               #    Gestão visual de passwords guardadas
│   ├── verificador.py               #    Verificador de força de password
│   ├── politicas.py                 #    Políticas de password configuráveis
│   └── utilizador.py                #    Perfil de utilizador (export, delete)
│
├── nginx/                           # ── Reverse proxy (Nginx) ──
│   ├── nginx.conf                   #    Config global (rate limit zones, timeouts)
│   ├── conf.d/
│   │   ├── auth.conf                #    TLS, security headers, proxy rules
│   │   └── proxy_params.conf        #    Parâmetros de proxy partilhados
│   └── certs/                       #    Certificados TLS (não commitados)
│
├── deploy/                          # ── Utilidades de deploy ──
│   ├── generate_secrets.py          #    Gerador de secrets criptográficos
│   ├── healthcheck.sh               #    Suite de validação pós-deploy
│   └── ufw_setup.sh                 #    Baseline de firewall UFW
│
├── docker/                          # ── Scripts operacionais Docker ──
│   └── scripts/
│       ├── deploy.sh                #    Deploy atómico com backup pré-deploy
│       ├── rollback.sh              #    Rollback instantâneo
│       ├── backup_db.sh             #    Backup local da base de dados
│       ├── backup_offsite.sh        #    Backup offsite
│       ├── restore_db.sh            #    Restauro de base de dados
│       ├── bootstrap.sh             #    Disaster recovery (rebuild completo)
│       ├── health_monitor.sh        #    Monitorização contínua de saúde
│       ├── alerts.sh                #    Notificações Discord/Telegram
│       └── harden_server.sh         #    Hardening SSH + fail2ban
│
├── certs/                           # ── Certificados (desktop) ──
│   └── server_ca.pem               #    CA cert para verificação TLS
│
├── data/                            # ── Dados persistentes ──
│   └── preferences.json             #    Preferências UI (tema, timeouts)
│
└── logs/                            # ── Logs da aplicação (gitignored) ──
```

---

## 🔧 Variáveis de Ambiente

### Cliente Desktop

| Variável | Default | Descrição |
|----------|---------|-----------|
| `API_BASE_URL` | `https://localhost:8000` | URL do servidor de autenticação |
| `API_TIMEOUT` | `10` | Timeout de requests HTTP (segundos) |

### Servidor de Autenticação

| Variável | Default | Descrição |
|----------|---------|-----------|
| `APP_ENV` | `development` | `development` ou `production` |
| `AUTH_JWT_SECRET` | *(obrigatório em prod)* | Secret para assinatura JWT (512 bits) |
| `AUTH_JWT_ALGORITHM` | `HS256` | Algoritmo JWT |
| `AUTH_DB_PATH` | `data/auth.db` | Caminho da base de dados SQLite |
| `AUTH_ACCESS_TOKEN_TTL_SECONDS` | `900` | Tempo de vida do access token (15 min) |
| `AUTH_REFRESH_TOKEN_TTL_SECONDS` | `604800` | Tempo de vida do refresh token (7 dias) |
| `AUTH_ISSUER` | `password-manager-auth` | Issuer nos claims JWT |
| `AUTH_AUDIENCE` | `password-manager-clients` | Audience nos claims JWT |
| `AUTH_LOGIN_MAX_FAILURES` | `5` | Tentativas antes de bloqueio |
| `AUTH_LOGIN_LOCKOUT_SECONDS` | `900` | Duração do bloqueio (15 min) |
| `AUTH_RATE_LIMIT_WINDOW_SECONDS` | `300` | Janela do rate limiter (5 min) |
| `AUTH_RATE_LIMIT_MAX_ATTEMPTS` | `10` | Máximo de tentativas na janela |
| `AUTH_PASSWORD_MIN_LENGTH` | `12` | Comprimento mínimo de password |
| `AUTH_LOG_FILE` | `/app/logs/auth.log` | Ficheiro de log do servidor |

---

## 🌐 Endpoints da API

### Autenticação

| Método | Path | Auth | Descrição |
|--------|------|------|-----------|
| `POST` | `/auth/register` | — | Criar conta (email + password + username) |
| `POST` | `/auth/login` | — | Login → JWT access + refresh token |
| `POST` | `/auth/refresh` | — | Rodar refresh token (rotation + reuse detection) |
| `POST` | `/auth/logout` | — | Revogar refresh token |
| `GET` | `/auth/me` | Bearer | Perfil do utilizador atual |
| `POST` | `/auth/change-password` | Bearer | Alterar password (requer password atual) |

### Verificação de Email

| Método | Path | Auth | Descrição |
|--------|------|------|-----------|
| `GET` | `/auth/verify-email` | — | Verificar email via token (link do email) |
| `POST` | `/auth/resend-verification` | — | Reenviar email de verificação |
| `GET` | `/auth/check-verified` | — | Verificar se email está confirmado |

### Vault (Zero-Knowledge)

| Método | Path | Auth | Descrição |
|--------|------|------|-----------|
| `POST` | `/vault/key` | Bearer | Guardar wrapped DEK + KEK salt (setup) |
| `GET` | `/vault/key` | Bearer | Obter material criptográfico do vault |
| `PUT` | `/vault/key` | Bearer | Re-wrap DEK (mudança de master password) |
| `GET` | `/vault/entries` | Bearer | Listar entradas encriptadas |
| `POST` | `/vault/entries` | Bearer | Criar nova entrada encriptada |
| `PUT` | `/vault/entries/{id}` | Bearer | Atualizar entrada encriptada |
| `DELETE` | `/vault/entries/{id}` | Bearer | Eliminar entrada |

### Administração (role=admin)

| Método | Path | Auth | Descrição |
|--------|------|------|-----------|
| `POST` | `/auth/admin/users` | Bearer (admin) | Listar todos os utilizadores |
| `POST` | `/auth/admin/user/active` | Bearer (admin) | Ativar/desativar conta |
| `POST` | `/auth/admin/user/reset-password` | Bearer (admin) | Reset password de utilizador |
| `POST` | `/auth/admin/user/delete` | Bearer (admin) | Eliminar conta de utilizador |
| `POST` | `/auth/admin/logs` | Bearer (admin) | Consultar logs de autenticação |
| `DELETE` | `/auth/account/delete` | Bearer | Eliminar a própria conta |

### Outros

| Método | Path | Auth | Descrição |
|--------|------|------|-----------|
| `GET` | `/health` | — | Health check do servidor |

---

## 🛡 Decisões de Segurança

| Decisão | Porquê |
|---------|--------|
| **Argon2id** (não bcrypt) | Vencedor do PHC, resistente a GPU/ASIC, recomendado OWASP |
| **JWT + refresh opaco** | Access curto (15 min) + refresh rotativo longo (7 dias) |
| **SHA-256 nos refresh tokens** | Leak da DB não compromete sessões ativas |
| **Deteção de reutilização** | Token roubado → revoga toda a família de tokens |
| **Constant-time em login falhado** | Sleep 350ms previne enumeração de users por timing |
| **Parameterized queries** | 100% das queries SQL usam `?` — imune a SQL injection |
| **Pydantic schemas** | Validação automática de input na fronteira da API |
| **AES-256-GCM + KEK/DEK** | Encriptação client-side, servidor nunca vê plaintext |
| **Security gate no startup** | Bloqueia produção com JWT secret fraco/default |
| **Docker non-root + read-only** | Limita blast radius de comprometimento do container |
| **Rate limiting duplo** | Defesa em profundidade: rede (Nginx) + aplicação (FastAPI) |
| **Rede Docker isolada** | Container auth sem portas expostas, só nginx comunica |

---

## 🛠 Stack Tecnológico

### Cliente Desktop

| Tecnologia | Versão | Propósito |
|------------|--------|-----------|
| Python | 3.11+ | Linguagem principal |
| Tkinter | stdlib | Interface gráfica desktop |
| requests | 2.32 | Cliente HTTP para a API |
| cryptography | 44.0+ | AES-256-GCM (vault encryption) |
| argon2-cffi | 23.1 | Key derivation (KDF) |
| python-dotenv | 1.2 | Variáveis de ambiente |

### Servidor

| Tecnologia | Versão | Propósito |
|------------|--------|-----------|
| FastAPI | 0.115 | Framework API REST |
| Uvicorn | 0.34 | Servidor ASGI (HTTP) |
| SQLite | WAL mode | Base de dados (zero-config) |
| Argon2id | 23.1 | Hash de passwords |
| PyJWT | 2.10 | Criação/validação de tokens JWT |
| Pydantic v2 | (via FastAPI) | Validação de schemas |

### Infraestrutura

| Tecnologia | Versão | Propósito |
|------------|--------|-----------|
| Docker | Compose v2 | Containerização |
| Nginx | 1.27 Alpine | Reverse proxy + TLS termination |
| Tailscale | — | VPN mesh (comunicação segura) |
| UFW | — | Firewall (Ubuntu) |
| fail2ban | — | Proteção contra brute-force SSH |

---

## 📄 Licença

Projeto académico — MIT License.

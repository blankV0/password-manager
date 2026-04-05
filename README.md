# 🔐 Password Manager

> Gestor de passwords seguro com cliente desktop e servidor de autenticação self-hosted — projeto académico com engenharia de nível profissional.

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://docs.docker.com/compose/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.0.0-brightgreen.svg)](VERSION)

---

## 📋 Índice

- [Visão Geral](#-visão-geral)
- [Funcionalidades](#-funcionalidades)
- [Tecnologias Utilizadas](#-tecnologias-utilizadas)
- [Arquitetura](#-arquitetura)
- [Instalação e Execução](#-instalação-e-execução)
- [Build para Executável (.exe)](#-build-para-executável-exe)
- [Deploy em Produção (Docker)](#-deploy-em-produção-docker)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [Boas Práticas de Segurança](#-boas-práticas-de-segurança)
- [Endpoints da API](#-endpoints-da-api)
- [Variáveis de Ambiente](#-variáveis-de-ambiente)
- [Licença](#-licença)

---

## 🎯 Visão Geral

O **Password Manager** é uma aplicação desktop desenvolvida em Python que permite aos utilizadores gerir as suas passwords de forma segura. A aplicação comunica com um servidor de autenticação self-hosted via HTTPS, garantindo que todas as credenciais são encriptadas ponto-a-ponto.

### Principais objetivos:

- **Segurança real** — encriptação AES-256-GCM com arquitetura zero-knowledge (o servidor nunca vê passwords em claro)
- **Facilidade de uso** — interface gráfica intuitiva com tema escuro/claro, sidebar de navegação e ações rápidas
- **Infraestrutura profissional** — servidor Docker com Nginx, TLS, rate limiting e hardening completo
- **Distribuição** — disponível como executável `.exe` para Windows (não requer Python instalado)

---

## ✨ Funcionalidades

### 🔒 Autenticação e Segurança

- Registo e login com passwords seguras (hash Argon2id, recomendado OWASP)
- Tokens JWT (15 min) + refresh tokens opacos (7 dias) com rotação automática
- Deteção de reutilização de refresh tokens (proteção contra roubo)
- Bloqueio de conta após 5 tentativas falhadas (lockout 15 min)
- Verificação de email via SMTP com token temporário (24h)
- Rate limiting duplo: aplicação (FastAPI) + rede (Nginx)

### 🔐 Gerenciador de Passwords (Vault)

- Encriptação **AES-256-GCM** — cada entrada é encriptada no cliente antes de ser enviada
- Arquitetura **KEK/DEK** — Master Password → Argon2id → KEK → unwrap DEK
- **Zero-knowledge** — o servidor guarda apenas ciphertext, nunca vê passwords em claro
- CRUD completo: criar, visualizar detalhes, editar e apagar credenciais
- Deteção de passwords fracas (vermelho) e repetidas (amarelo)
- Copiar password para clipboard com limpeza automática (30s)
- Importação e exportação de credenciais em formato JSON

### 🖥️ Interface Desktop

- **Dashboard** com estatísticas do vault e ações rápidas
- **Gerador** de passwords configurável (comprimento, letras, números, símbolos)
- **Verificador** de força de passwords em tempo real com checklist visual
- **Utilizador** — perfil com estatísticas, exportação/importação e eliminação de dados
- **Definições** — tema escuro/claro, timeouts e zona de perigo
- **Painel Admin** — gestão de utilizadores (ativar/desativar, reset password, eliminar)
- Sidebar com realce visual da página ativa
- Barra de título customizada sem titlebar nativa (Windows)

### 🐳 Infraestrutura

- **Docker Compose** — containers non-root, filesystem read-only, no-new-privileges
- **Nginx** — TLS 1.2/1.3, HSTS, CSP, X-Frame-Options, `/docs` bloqueado em produção
- **Rede isolada** — container auth sem portas expostas, só nginx comunica
- Deploy atómico com backup pré-deploy e rollback instantâneo
- Health checks automáticos e scripts de monitorização
- Backups SQLite automatizados + scripts de restore

---

## 🛠 Tecnologias Utilizadas

### Cliente Desktop

| Tecnologia | Versão | Propósito |
|------------|--------|-----------|
| Python | 3.11+ | Linguagem principal |
| Tkinter | stdlib | Interface gráfica |
| requests | 2.32 | Cliente HTTP |
| cryptography | 44.0+ | AES-256-GCM (encriptação do vault) |
| argon2-cffi | 23.1 | Key derivation (Argon2id) |
| python-dotenv | 1.2 | Variáveis de ambiente |
| PyInstaller | 6.17 | Build para executável .exe |

### Servidor

| Tecnologia | Versão | Propósito |
|------------|--------|-----------|
| FastAPI | 0.115 | Framework API REST |
| Uvicorn | 0.34 | Servidor ASGI |
| SQLite | WAL mode | Base de dados |
| Argon2id | 23.1 | Hash de passwords |
| PyJWT | 2.10 | Tokens JWT |
| Pydantic v2 | (via FastAPI) | Validação de schemas |

### Infraestrutura

| Tecnologia | Propósito |
|------------|-----------|
| Docker Compose | Containerização e orquestração |
| Nginx Alpine | Reverse proxy + TLS termination |
| Tailscale | VPN mesh para comunicação segura |
| UFW + fail2ban | Firewall e proteção brute-force |

---

## 🏗 Arquitetura

```
┌──────────────────────────────────────────────────────────────┐
│                    CLIENTE DESKTOP (Tkinter)                 │
│                                                              │
│  Login/Registo → Dashboard → Sidebar (7 páginas)             │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  Gerenciador (Vault) — Encriptação client-side       │    │
│  │  AES-256-GCM · KEK/DEK · Argon2id                   │    │
│  │  Servidor NUNCA vê passwords em claro                │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  local_auth.py → HTTP client (login, vault CRUD, admin)      │
└─────────────────────┬────────────────────────────────────────┘
                      │ HTTPS (TLS 1.2/1.3 via Tailscale VPN)
                      ▼
┌──────────────────────────────────────────────────────────────┐
│               SERVIDOR DE PRODUÇÃO (Docker)                  │
│                                                              │
│  Nginx (Alpine)           FastAPI + Uvicorn                  │
│  ┌──────────────┐         ┌──────────────────────┐           │
│  │ TLS          │         │ /auth/* (JWT, Argon2) │           │
│  │ Rate limit   │────────▶│ /vault/* (ciphertext) │           │
│  │ HSTS, CSP    │         │ /admin/* (role=admin) │           │
│  └──────────────┘         └──────────┬───────────┘           │
│                                      │                       │
│                           ┌──────────▼───────────┐           │
│                           │ SQLite (WAL mode)    │           │
│                           │ users, vault_entries │           │
│                           │ vault_keys, tokens   │           │
│                           └──────────────────────┘           │
│                                                              │
│  Segurança: non-root, read-only fs, no-new-privileges       │
│  Rede: container auth isolado (pm_internal)                  │
└──────────────────────────────────────────────────────────────┘
```

---

## 🚀 Instalação e Execução

### Pré-requisitos

- **Python 3.11+** instalado
- **pip** (gestor de pacotes Python)
- **Tailscale** instalado e ligado (para acesso ao servidor de autenticação)

### 1. Clonar o repositório

```bash
git clone https://github.com/blankV0/password-manager.git
cd password-manager
```

### 2. Criar ambiente virtual e instalar dependências

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Configurar variáveis de ambiente

```bash
cp .env.example .env
```

Editar o ficheiro `.env` e configurar:

```dotenv
API_BASE_URL=https://<IP_TAILSCALE_DO_SERVIDOR>
```

### 4. Executar

```bash
python main.py
```

A aplicação abre a janela de login. Após autenticação, acede-se ao dashboard completo.

---

## 📦 Build para Executável (.exe)

Para distribuir a aplicação sem necessidade de Python instalado:

### 1. Instalar PyInstaller

```bash
pip install pyinstaller
```

### 2. Gerar o executável

```bash
pyinstaller PasswordManager.spec --noconfirm
```

### 3. Copiar ficheiros necessários

Após o build, copiar para `dist/PasswordManager/` (ao lado do `.exe`):

```
dist/PasswordManager/
├── PasswordManager.exe    ← executável principal
├── .env                   ← configuração (API_BASE_URL)
├── data/                  ← preferences.json
├── certs/                 ← server_ca.pem (certificado TLS)
├── gerador1/              ← módulos do gerador
└── logs/                  ← (criado automaticamente)
```

### 4. Executar

Basta abrir `PasswordManager.exe` — funciona sem Python instalado.

---

## 🐳 Deploy em Produção (Docker)

### 1. Instalar Docker

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER && newgrp docker
```

### 2. Configurar secrets

```bash
cp .env.example .env
python deploy/generate_secrets.py
# Configurar AUTH_JWT_SECRET e APP_ENV=production no .env
```

### 3. Certificado TLS

Colocar certificados em `nginx/certs/`:
- `fullchain.pem`
- `privkey.pem`

### 4. Firewall e deploy

```bash
sudo ./deploy/ufw_setup.sh
docker compose build && docker compose up -d
```

### 5. Validar

```bash
./deploy/healthcheck.sh --host https://<hostname>
```

---

## 📁 Estrutura do Projeto

```
password-manager/
├── main.py                          # Entry point — app desktop (Tkinter)
├── auth_server.py                   # Entry point — FastAPI auth server
├── PasswordManager.spec             # Configuração PyInstaller (.exe build)
├── requirements.txt                 # Dependências (desktop)
├── requirements.server.txt          # Dependências (servidor Docker)
├── docker-compose.yml               # Orquestração Docker
├── Dockerfile                       # Build do container (multi-stage)
├── .env.example                     # Template de variáveis de ambiente
├── VERSION                          # Versão semântica (1.0.0)
├── CHANGELOG.md                     # Histórico de alterações
│
├── src/                             # ── Código-fonte principal ──
│   ├── auth/                        # Módulo servidor (FastAPI)
│   │   ├── api.py                   #   Endpoints REST (auth, admin)
│   │   ├── service.py               #   Lógica de negócio (AuthService)
│   │   ├── database.py              #   Schema SQLite, migrações
│   │   ├── schemas.py               #   Modelos Pydantic
│   │   ├── tokens.py                #   JWT + refresh tokens
│   │   ├── passwords.py             #   Argon2id hash/verify
│   │   ├── config.py                #   Settings do servidor
│   │   ├── rate_limiter.py          #   Sliding-window limiter
│   │   ├── email_service.py         #   SMTP (verificação email)
│   │   ├── vault_api.py             #   Endpoints vault (zero-knowledge)
│   │   └── vault_schemas.py         #   Schemas do vault
│   │
│   ├── config/                      # Configuração (desktop)
│   │   └── settings.py              #   Settings centralizados
│   │
│   ├── core/                        # Camada criptográfica
│   │   ├── crypto.py                #   CryptoProvider (KEK/DEK)
│   │   ├── encryption.py            #   AES-256-GCM
│   │   ├── key_derivation.py        #   Argon2id KDF
│   │   └── secure_memory.py         #   Limpeza segura de memória
│   │
│   ├── models/                      # Modelos (desktop)
│   │   └── local_auth.py            #   Cliente HTTP para a API
│   │
│   ├── services/                    # Serviços auxiliares
│   │   ├── email_verification.py    #   Fluxo verificação email
│   │   └── sms_verification.py      #   Verificação SMS
│   │
│   ├── storage/                     # Vault crypto
│   │   └── vault_crypto.py          #   Operações criptográficas
│   │
│   ├── ui/                          # Interface gráfica (Tkinter)
│   │   ├── login_gui.py             #   Login, registo, verificação
│   │   ├── vault_gui.py             #   Gerenciador (VaultPage)
│   │   ├── settings_page.py         #   Definições (tema, zona perigo)
│   │   └── admin_panel.py           #   Painel de administração
│   │
│   └── utils/                       # Utilitários
│       ├── logging_config.py        #   Logging estruturado
│       └── security_validator.py    #   Validação + masking PII
│
├── gerador1/                        # ── Módulos do gerador ──
│   ├── inicio.py                    #   Dashboard (stats, ações rápidas)
│   ├── gerador.py                   #   Gerador de passwords
│   ├── verificador.py               #   Verificador de força
│   ├── utilizador.py                #   Perfil (export/import/delete)
│   └── politicas.py                 #   Políticas de password
│
├── nginx/                           # ── Reverse proxy ──
│   ├── nginx.conf                   #   Config global
│   └── conf.d/                      #   TLS, headers, proxy rules
│
├── deploy/                          # ── Utilidades de deploy ──
│   ├── generate_secrets.py          #   Gerador de secrets
│   ├── healthcheck.sh               #   Validação pós-deploy
│   └── ufw_setup.sh                 #   Firewall UFW
│
├── docker/scripts/                  # ── Scripts operacionais ──
│   ├── deploy.sh                    #   Deploy atómico
│   ├── rollback.sh                  #   Rollback instantâneo
│   ├── backup_db.sh                 #   Backup local
│   └── bootstrap.sh                 #   Disaster recovery
│
├── certs/                           # Certificados TLS (desktop)
├── data/                            # Dados persistentes
└── logs/                            # Logs (gitignored)
```

---

## 🛡 Boas Práticas de Segurança

### Encriptação e Autenticação

| Prática | Implementação |
|---------|---------------|
| Hash de passwords | **Argon2id** (vencedor PHC, resistente a GPU/ASIC) — `time_cost=3, memory_cost=64 MiB` |
| Encriptação do vault | **AES-256-GCM** com arquitetura KEK/DEK — encriptação client-side |
| Zero-knowledge | Servidor guarda apenas ciphertext — nunca vê passwords em claro |
| Tokens JWT | Access curto (15 min) + refresh opaco rotativo (7 dias) |
| Refresh tokens | Apenas SHA-256 do token guardado na DB — leak da DB não compromete sessões |
| Deteção de reutilização | Token roubado → revoga toda a família de tokens |

### Proteção contra Ataques

| Prática | Implementação |
|---------|---------------|
| SQL Injection | **Imune** — 100% parameterized queries (`?` placeholders) |
| Brute-force | Lockout (5 falhas → 15 min) + rate limiting duplo (Nginx + FastAPI) |
| Timing attacks | Sleep constante (350ms) em login falhado — previne enumeração de utilizadores |
| Input validation | **Pydantic** schemas com validações estritas na fronteira da API |
| Security gate | Recusa iniciar em produção com JWT secret fraco/default |

### Infraestrutura

| Prática | Implementação |
|---------|---------------|
| Docker hardening | Non-root, read-only filesystem, no-new-privileges |
| Rede isolada | Container auth sem portas expostas — só Nginx comunica |
| TLS | 1.2/1.3 via Nginx com HSTS, CSP, X-Frame-Options |
| Firewall | UFW (deny default) + fail2ban (SSH brute-force) |
| API docs | Bloqueados em produção (`/docs`, `/redoc`, `/openapi.json`) |
| Audit trail | Todos os eventos de autenticação registados na DB + logs |

---

## 🌐 Endpoints da API

### Autenticação

| Método | Path | Descrição |
|--------|------|-----------|
| `POST` | `/auth/register` | Criar conta |
| `POST` | `/auth/login` | Login → JWT + refresh token |
| `POST` | `/auth/refresh` | Rodar refresh token |
| `POST` | `/auth/logout` | Revogar refresh token |
| `GET` | `/auth/me` | Perfil do utilizador |
| `POST` | `/auth/change-password` | Alterar password |

### Verificação de Email

| Método | Path | Descrição |
|--------|------|-----------|
| `GET` | `/auth/verify-email` | Verificar email (link) |
| `POST` | `/auth/resend-verification` | Reenviar email |
| `GET` | `/auth/check-verified` | Verificar estado |

### Vault (Zero-Knowledge)

| Método | Path | Descrição |
|--------|------|-----------|
| `POST` | `/vault/key` | Setup — guardar KEK salt + wrapped DEK |
| `GET` | `/vault/key` | Obter material criptográfico |
| `GET` | `/vault/entries` | Listar entradas encriptadas |
| `POST` | `/vault/entries` | Criar entrada |
| `PUT` | `/vault/entries/{id}` | Atualizar entrada |
| `DELETE` | `/vault/entries/{id}` | Eliminar entrada |

### Administração (role=admin)

| Método | Path | Descrição |
|--------|------|-----------|
| `POST` | `/auth/admin/users` | Listar utilizadores |
| `POST` | `/auth/admin/user/active` | Ativar/desativar conta |
| `POST` | `/auth/admin/user/reset-password` | Reset password |
| `POST` | `/auth/admin/user/delete` | Eliminar utilizador |
| `POST` | `/auth/admin/logs` | Consultar logs |
| `DELETE` | `/auth/account/delete` | Eliminar própria conta |

---

## 🔧 Variáveis de Ambiente

### Cliente Desktop (`.env`)

| Variável | Default | Descrição |
|----------|---------|-----------|
| `API_BASE_URL` | `https://localhost:8000` | URL do servidor de autenticação |
| `API_TIMEOUT` | `10` | Timeout HTTP (segundos) |

### Servidor de Autenticação (`.env`)

| Variável | Default | Descrição |
|----------|---------|-----------|
| `APP_ENV` | `development` | Ambiente (`production` bloqueia /docs) |
| `AUTH_JWT_SECRET` | *(obrigatório)* | Secret JWT (512 bits) |
| `AUTH_DB_PATH` | `data/auth.db` | Caminho da base de dados |
| `AUTH_ACCESS_TOKEN_TTL_SECONDS` | `900` | TTL access token (15 min) |
| `AUTH_REFRESH_TOKEN_TTL_SECONDS` | `604800` | TTL refresh token (7 dias) |
| `AUTH_LOGIN_MAX_FAILURES` | `5` | Tentativas antes de bloqueio |
| `AUTH_LOGIN_LOCKOUT_SECONDS` | `900` | Duração do bloqueio (15 min) |
| `AUTH_PASSWORD_MIN_LENGTH` | `12` | Comprimento mínimo de password |

---

## 📄 Licença

Projeto académico — MIT License.

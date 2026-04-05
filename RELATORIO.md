# Relatório do Projeto — Password Manager v1.0.0

**Disciplina:** Projeto de Escola  
**Data:** Abril 2026  
**Versão:** 1.0.0  
**Repositório:** https://github.com/blankV0/password-manager

---

## 1. Introdução

O presente relatório documenta o desenvolvimento do **Password Manager**, uma aplicação desktop de gestão de passwords com servidor de autenticação self-hosted. O projeto foi desenvolvido como trabalho académico, aplicando princípios de engenharia de software, criptografia moderna e boas práticas de segurança.

A aplicação permite aos utilizadores registar-se, autenticar-se e guardar credenciais de forma segura, utilizando encriptação ponto-a-ponto (zero-knowledge). O servidor nunca tem acesso às passwords em claro — toda a encriptação e desencriptação acontece exclusivamente no cliente.

---

## 2. Objetivos do Projeto

- Desenvolver uma aplicação desktop funcional para gestão segura de passwords
- Implementar autenticação robusta com hashing Argon2id e tokens JWT
- Encriptar todas as credenciais com AES-256-GCM antes de enviar ao servidor
- Disponibilizar uma interface gráfica intuitiva com múltiplas funcionalidades
- Fazer deploy do servidor em Docker com Nginx, TLS e hardening de segurança
- Distribuir a aplicação como executável `.exe` para Windows

---

## 3. Arquitetura do Sistema

O sistema é composto por dois componentes principais:

### 3.1 Cliente Desktop (Tkinter)

A aplicação desktop foi desenvolvida em Python com Tkinter como framework de interface gráfica. É composta por:

- **Login e Registo** — autenticação segura com verificação de email
- **Dashboard** — página inicial com estatísticas do vault
- **Gerenciador** — CRUD de credenciais encriptadas (vault)
- **Gerador** — geração de passwords configuráveis
- **Verificador** — análise de força de passwords em tempo real
- **Utilizador** — perfil, exportação/importação de dados
- **Definições** — tema escuro/claro, timeouts, zona de perigo
- **Painel Admin** — gestão de utilizadores (apenas role admin)

A comunicação com o servidor é feita via HTTPS sobre VPN Tailscale. O módulo `local_auth.py` centraliza todas as chamadas HTTP, gestão de tokens JWT e refresh tokens.

### 3.2 Servidor de Autenticação (FastAPI + Docker)

O servidor foi desenvolvido com FastAPI e está deployed em Docker com:

- **Nginx** como reverse proxy (TLS termination, rate limiting, security headers)
- **Container auth** isolado na rede interna (sem portas expostas para o host)
- **SQLite** em modo WAL como base de dados
- **Volumes Docker** para persistência de dados e logs

A base de dados contém as seguintes tabelas:
- `users` — dados de autenticação (email, username, password hash, role, estado)
- `vault_keys` — material criptográfico do vault (KEK salt, wrapped DEK)
- `vault_entries` — entradas encriptadas (ciphertext, nonce, tag)
- `refresh_tokens` — hash SHA-256 dos refresh tokens ativos
- `auth_events` — log de todos os eventos de autenticação
- `email_verifications` — tokens de verificação de email

### 3.3 Diagrama de Arquitetura

```
Cliente (Tkinter)                    Servidor (Docker)
┌─────────────────┐                 ┌──────────────────┐
│                 │    HTTPS/TLS    │     Nginx        │
│  UI + Crypto    │────────────────▶│  (rate limit)    │
│  AES-256-GCM    │                 │       │          │
│  KEK / DEK      │                 │       ▼          │
│                 │                 │  FastAPI (auth)  │
│  Encriptação    │                 │       │          │
│  client-side    │                 │       ▼          │
│                 │                 │  SQLite (WAL)    │
└─────────────────┘                 └──────────────────┘

Zero-knowledge: servidor guarda APENAS ciphertext
```

---

## 4. Funcionalidades Implementadas

### 4.1 Autenticação

O sistema de autenticação implementa:

- **Registo** com validação de email, username e password (mínimo 12 caracteres, maiúsculas, números, símbolos)
- **Login** com proteção contra brute-force (lockout após 5 tentativas falhadas, 15 minutos)
- **Tokens JWT** com TTL de 15 minutos para access tokens
- **Refresh tokens opacos** com TTL de 7 dias e rotação automática
- **Deteção de reutilização** de refresh tokens — se um token roubado for usado, toda a família é revogada
- **Verificação de email** via SMTP com token temporário (24h)
- **Constant-time response** em login falhado (350ms sleep) para prevenir enumeração de utilizadores

### 4.2 Gerenciador de Passwords (Vault)

O gerenciador é a funcionalidade central da aplicação:

- **Encriptação AES-256-GCM** — cada entrada é encriptada no cliente com uma DEK (Data Encryption Key) aleatória
- **Arquitetura KEK/DEK** — a master password do utilizador é derivada via Argon2id (time_cost=3, memory_cost=64 MiB) para criar uma KEK que protege a DEK
- **CRUD completo** — criar, visualizar detalhes (read-only), editar e apagar credenciais
- **Deteção de passwords fracas** — entries com passwords fracas aparecem a vermelho na tabela
- **Deteção de passwords repetidas** — entries com a mesma password aparecem a amarelo
- **Copiar para clipboard** — com limpeza automática do clipboard após 30 segundos
- **Importação/Exportação** — ficheiros JSON para backup e migração de dados
- **Pesquisa** — filtro em tempo real por serviço, utilizador ou notas

### 4.3 Gerador de Passwords

O gerador permite criar passwords aleatórias com configuração de:
- Comprimento (8 a 128 caracteres)
- Inclusão de letras maiúsculas e minúsculas
- Inclusão de números
- Inclusão de símbolos especiais
- Botão para guardar diretamente no gerenciador

### 4.4 Verificador de Força

O verificador analisa passwords em tempo real e apresenta:
- Barra de força visual (vermelho → laranja → amarelo → verde)
- Checklist de requisitos (comprimento, maiúsculas, números, símbolos)
- Feedback instantâneo enquanto o utilizador digita

### 4.5 Interface Gráfica

A interface foi desenvolvida com atenção ao detalhe:
- **Tema escuro e claro** — selecionável nas definições, aplicado globalmente
- **Sidebar** com navegação entre 7 páginas e realce visual da página ativa
- **Barra de título customizada** — sem titlebar nativa do Windows, com botões de minimizar e fechar
- **Drag manual** para mover a janela (substituição do drag Win32 para evitar bug de growing window)
- **Diálogos separados** — visualização (read-only) e edição são ações distintas para evitar alterações acidentais

### 4.6 Painel de Administração

Disponível apenas para utilizadores com role `admin`:
- Listar todos os utilizadores registados
- Ativar/desativar contas
- Reset de password de utilizadores
- Eliminar contas
- Consultar logs de autenticação

### 4.7 Gestão de Conta

O utilizador pode:
- Ver estatísticas das credenciais guardadas
- Exportar credenciais em formato JSON
- Importar credenciais de ficheiro JSON
- Alterar password
- Eliminar a sua própria conta (com confirmação)

---

## 5. Tecnologias Utilizadas

### 5.1 Cliente Desktop

| Tecnologia | Versão | Propósito |
|------------|--------|-----------|
| Python | 3.11+ | Linguagem principal |
| Tkinter | stdlib | Interface gráfica desktop |
| requests | 2.32.3 | Cliente HTTP para a API |
| cryptography | 44.0+ | AES-256-GCM (encriptação do vault) |
| argon2-cffi | 23.1.0 | Key derivation function (Argon2id) |
| python-dotenv | 1.2.1 | Gestão de variáveis de ambiente |
| PyInstaller | 6.17.0 | Build para executável .exe |

### 5.2 Servidor

| Tecnologia | Versão | Propósito |
|------------|--------|-----------|
| FastAPI | 0.115.12 | Framework API REST |
| Uvicorn | 0.34.0 | Servidor ASGI (HTTP) |
| SQLite | WAL mode | Base de dados (zero-config) |
| argon2-cffi | 23.1.0 | Hash de passwords (Argon2id) |
| PyJWT | 2.10.1 | Criação e validação de tokens JWT |
| Pydantic v2 | (via FastAPI) | Validação de schemas de input |
| email-validator | 2.2.0 | Validação de endereços de email |

### 5.3 Infraestrutura

| Tecnologia | Propósito |
|------------|-----------|
| Docker Compose | Containerização e orquestração de serviços |
| Nginx (Alpine) | Reverse proxy, TLS termination, rate limiting |
| Tailscale | VPN mesh para comunicação segura cliente-servidor |
| UFW | Firewall (deny by default, allow 22/80/443) |
| fail2ban | Proteção contra brute-force SSH |

---

## 6. Segurança

A segurança foi uma prioridade fundamental ao longo de todo o desenvolvimento.

### 6.1 Encriptação do Vault

A arquitetura de encriptação segue o modelo KEK/DEK (Key Encryption Key / Data Encryption Key):

1. O utilizador fornece a master password
2. A master password é derivada com **Argon2id** (time_cost=3, memory_cost=64 MiB, parallelism=2) para gerar a KEK
3. Uma DEK aleatória (256 bits) é gerada e wrapped (encriptada) com a KEK
4. Cada entrada do vault é encriptada com **AES-256-GCM** usando a DEK
5. O servidor guarda apenas: ciphertext + nonce + tag + wrapped DEK + KEK salt
6. O servidor **nunca** tem acesso às passwords em claro (zero-knowledge)

### 6.2 Hashing de Passwords

As passwords de autenticação são protegidas com **Argon2id**, o algoritmo recomendado pela OWASP:
- Resistente a ataques GPU e ASIC
- Vencedor do Password Hashing Competition (PHC)
- Parâmetros: time_cost=3, memory_cost=64 MiB

### 6.3 Proteção contra Ataques

| Ataque | Mitigação |
|--------|-----------|
| SQL Injection | 100% parameterized queries (? placeholders) |
| Brute-force (login) | Lockout após 5 falhas + rate limiting duplo |
| Brute-force (SSH) | fail2ban + password auth disabled |
| Token theft | Rotação de refresh tokens + deteção de reutilização |
| Timing attacks | Constant-time response (350ms) em login falhado |
| Man-in-the-middle | TLS 1.2/1.3 via Nginx + HSTS |
| Container escape | Non-root, read-only FS, no-new-privileges |
| Rede lateral | Container auth isolado, sem portas expostas |

### 6.4 Hardening do Servidor

- Docker: non-root user, read-only filesystem, no-new-privileges
- Nginx: HSTS, CSP, X-Frame-Options, X-Content-Type-Options
- API docs (`/docs`, `/redoc`, `/openapi.json`) bloqueados em produção
- Rede Docker isolada — container auth sem acesso direto ao host
- Firewall UFW com deny default
- SSH hardening: password auth disabled, MaxAuthTries 3

---

## 7. Estrutura do Projeto

O projeto segue uma arquitetura modular organizada por responsabilidade:

```
password-manager/
├── main.py                    # Entry point (desktop)
├── auth_server.py             # Entry point (servidor)
├── PasswordManager.spec       # Build PyInstaller
├── requirements.txt           # Dependências desktop
├── requirements.server.txt    # Dependências servidor
├── docker-compose.yml         # Orquestração Docker
├── Dockerfile                 # Build do container
│
├── src/                       # Código-fonte
│   ├── auth/                  # Servidor FastAPI (11 ficheiros)
│   ├── config/                # Configurações centralizadas
│   ├── core/                  # Camada criptográfica (4 ficheiros)
│   ├── models/                # Cliente HTTP (local_auth.py)
│   ├── services/              # Email e SMS verification
│   ├── storage/               # Vault crypto operations
│   ├── ui/                    # Interface gráfica (4 ficheiros)
│   └── utils/                 # Logging e validação
│
├── gerador1/                  # Módulos do gerador (5 ficheiros)
├── nginx/                     # Configuração Nginx
├── deploy/                    # Scripts de deploy
├── docker/scripts/            # Scripts operacionais
├── certs/                     # Certificados TLS
├── data/                      # Dados persistentes
└── logs/                      # Logs da aplicação
```

### Estatísticas do Código

| Métrica | Valor |
|---------|-------|
| Ficheiros Python | ~30 |
| Linhas de código | ~8.000+ |
| Módulos/pacotes | 8 (auth, config, core, models, services, storage, ui, utils) |
| Endpoints API | 18 |
| Tabelas SQLite | 6 |
| Dependências | 15 (cliente) + 6 (servidor) |

---

## 8. Definições (Settings)

A página de Definições permite ao utilizador personalizar a aplicação:

- **Tema** — alternância entre tema escuro e claro, aplicado globalmente a todos os componentes da interface
- **Zona de perigo** — ações destrutivas como alterar password e eliminar conta, com confirmações múltiplas

A implementação utiliza um ficheiro `data/preferences.json` para persistir as preferências do utilizador entre sessões. A troca de tema reconstrói todo o dashboard para aplicar as novas cores de forma consistente.

As configurações do servidor e da API são geridas via variáveis de ambiente no ficheiro `.env`, seguindo o princípio 12-factor app (configuração separada do código).

---

## 9. Login e Registo

### 9.1 Ecrã de Login

O login apresenta um layout split-screen:
- Lado esquerdo: branding e descrição da aplicação
- Lado direito: formulário de autenticação (email + password)

Inclui validação de campos em tempo real e feedback visual de erros. Após login bem-sucedido, o utilizador é redirecionado para o dashboard.

### 9.2 Ecrã de Registo

O registo requer:
- Email válido (verificado via SMTP)
- Username (3-30 caracteres)
- Password segura (mínimo 12 caracteres, maiúsculas, números, símbolos)

Após registo, é enviado um email de verificação com token temporário (24h). O utilizador deve verificar o email antes de poder aceder ao vault.

### 9.3 Verificação de Email

O fluxo de verificação:
1. Utilizador regista-se → servidor envia email com link de verificação
2. Link contém token único com TTL de 24h
3. Utilizador clica no link → email marcado como verificado
4. Acesso ao vault só é permitido após verificação

---

## 10. Base de Dados

### 10.1 Schema

A base de dados SQLite contém 6 tabelas:

**users** — informação de autenticação
- `id`, `email`, `username`, `password_hash` (Argon2id), `role`, `is_active`, `email_verified`, `failed_login_attempts`, `locked_until`, `created_at`, `updated_at`

**vault_keys** — material criptográfico do vault
- `user_id`, `kek_salt_b64`, `wrapped_dek_b64`, `dek_nonce_b64`, `dek_tag_b64`

**vault_entries** — credenciais encriptadas
- `id`, `user_id`, `encrypted_data_b64`, `nonce_b64`, `tag_b64`, `created_at`, `updated_at`

**refresh_tokens** — tokens de sessão (apenas hash)
- `id`, `user_id`, `token_hash` (SHA-256), `expires_at`, `created_at`

**auth_events** — auditoria de eventos
- `id`, `user_id`, `event_type`, `ip_address`, `created_at`

**email_verifications** — tokens de verificação
- `id`, `user_id`, `token`, `expires_at`, `verified_at`

### 10.2 Segurança da Base de Dados

- SQLite em modo WAL (Write-Ahead Logging) para melhor performance e concorrência
- Volume Docker persistente (`auth_data:/app/data`)
- Backups automatizados a cada 6h com scripts de restore
- Passwords guardadas como hash Argon2id (nunca em claro)
- Credenciais do vault guardadas como ciphertext AES-256-GCM (nunca em claro)

---

## 11. Painel de Administração

O painel de administração está disponível apenas para utilizadores com `role=admin` e permite:

- **Listar utilizadores** — ver todos os utilizadores registados com email, username, role, estado e data de criação
- **Ativar/Desativar** — bloquear ou desbloquear contas de utilizadores
- **Reset password** — gerar nova password temporária para um utilizador
- **Eliminar** — remover permanentemente uma conta e todos os seus dados
- **Logs** — consultar o histórico de eventos de autenticação (login, registo, falhas)

O acesso ao painel é validado tanto no cliente (botão só visível para admins) como no servidor (endpoints protegidos por JWT com verificação de role).

---

## 12. Build e Distribuição

### 12.1 Executável (.exe)

A aplicação é distribuída como executável Windows usando PyInstaller:

- **Modo onedir** — pasta `dist/PasswordManager/` com o .exe e todas as dependências
- **Sem consola** — modo windowed (sem janela de terminal)
- **Suporte frozen** — o código deteta quando está a correr como .exe via `sys.frozen` e ajusta os caminhos de ficheiros (`.env`, `data/`, `certs/`, `logs/`)
- **Tamanho** — ~12 MB o executável, ~52 MB a pasta completa

### 12.2 Deploy do Servidor

O servidor é deployed via Docker Compose com:
- Build multi-stage para imagem mínima
- Container auth isolado na rede interna
- Nginx como reverse proxy com TLS
- Volumes persistentes para dados e logs
- Scripts de deploy atómico, rollback e backup

---

## 13. Desafios e Soluções

### 13.1 Encriptação Zero-Knowledge

**Desafio:** Guardar passwords no servidor sem que este tenha acesso a elas.  
**Solução:** Implementação de arquitetura KEK/DEK com AES-256-GCM — toda a encriptação acontece no cliente. O servidor guarda apenas blobs criptográficos opacos.

### 13.2 Caminhos em .exe (PyInstaller)

**Desafio:** Quando a aplicação corre como `.exe`, `Path(__file__)` aponta para `_internal/` em vez da pasta do executável, causando falhas ao encontrar `.env`, certificados e dados.  
**Solução:** Implementação de deteção `sys.frozen` em 4 ficheiros críticos, usando `Path(sys.executable).resolve().parent` como `APP_ROOT`.

### 13.3 Growing Window Bug

**Desafio:** Ao mover a janela (drag), esta crescia progressivamente para a direita devido ao uso de `WM_NCLBUTTONDOWN` + `HTCAPTION` do Win32 com a titlebar nativa removida.  
**Solução:** Substituição do drag Win32 por drag manual Tkinter que altera apenas a posição (`+x+y`), nunca o tamanho. Complementado com `resizable(False, False)` e `minsize`/`maxsize`.

### 13.4 Refresh Token Security

**Desafio:** Se um refresh token for roubado, o atacante pode obter access tokens indefinidamente.  
**Solução:** Rotação automática de refresh tokens — cada uso gera um novo token e invalida o anterior. Se um token já usado for reutilizado, toda a família de tokens é revogada (deteção de reutilização).

---

## 14. Conclusão

O Password Manager v1.0.0 cumpre todos os objetivos propostos:

- ✅ Aplicação desktop funcional com interface gráfica completa
- ✅ Autenticação robusta com Argon2id, JWT e refresh tokens
- ✅ Encriptação zero-knowledge com AES-256-GCM
- ✅ Servidor deployed em Docker com hardening de segurança
- ✅ Distribuição como executável .exe para Windows
- ✅ Documentação completa (README, relatório, CHANGELOG)

O projeto demonstra a aplicação prática de conceitos de:
- Engenharia de software (arquitetura modular, separação de responsabilidades)
- Criptografia moderna (AES-256-GCM, Argon2id, KEK/DEK)
- Segurança informática (OWASP, hardening, zero-knowledge)
- DevOps (Docker, Nginx, TLS, deploy automatizado)
- Interface humano-computador (UX/UI com Tkinter)

---

*Fim do Relatório*

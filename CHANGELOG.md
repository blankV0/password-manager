# Changelog

Todas as alterações notáveis neste projecto serão documentadas aqui.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projecto segue [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [1.0.0] - 2025-07-25

### Resumo
Versão final do projecto académico — auditoria de segurança completa, refactoring
profundo, e fundação criptográfica para o vault local.

### Adicionado
- `src/core/` — Camada criptográfica completa (AES-256-GCM, Argon2id KDF, KEK/DEK)
  - `crypto.py` — CryptoProvider (derive_kek, generate_dek, wrap/unwrap, encrypt/decrypt_entry)
  - `encryption.py` — AES-256-GCM com nonce aleatório e authentication tag
  - `key_derivation.py` — Argon2id (t=3, m=64 MiB, p=2, 32 bytes)
  - `secure_memory.py` — secure_zero() via ctypes.memset + SecureBytes RAII
- `src/storage/` — Pacote preparado para persistência encriptada do vault
- `__version__ = "1.0.0"` em `src/__init__.py`
- CI/CD pipeline com GitHub Actions (deploy automático via SSH)
- Sistema de alertas Discord/Telegram (`scripts/alerts.sh`)
- Deploy atómico com backup pré-deploy e rollback (`scripts/deploy.sh`)
- Script de rollback rápido (`scripts/rollback.sh`)
- Backups offsite (`scripts/backup_offsite.sh`)
- Bootstrap completo para disaster recovery (`scripts/bootstrap.sh`)
- Guia de disaster recovery (`DISASTER_RECOVERY.md`)
- Versionamento semântico com tags

### Segurança (Auditoria V1.0)
- Removidas credenciais Twilio hardcoded de `config.json`
- Eliminados todos os `verify=False` (SSL) — substituído por verificação com CA cert
- Removida password de admin hardcoded em `settings.py`
- Limpo `CORS_ORIGINS` default (já não inclui `*`)
- Removido `debug_mode` em `settings.py` (controlado apenas por `.env`)
- `PASSWORD_MIN_LENGTH` corrigido de 8 → 12 em todas as localizações
- Todas as chamadas `logging.*(f"...")` convertidas para `%s`-style (anti log-injection)
- Removido `email_service.py` (código morto, duplicava `email_verification.py`)
- Removido `config_manager.py` (código morto, substituído por `settings.py` + `.env`)
- Removido ~515 linhas de dashboard duplicado em `login_gui.py` (1210 → 695 linhas)
- Removido security theatre de `security_validator.py` (CSRF, device fingerprint, session tokens falsos)
- Removidos 3 métodos dead-code de `login_gui.py` (`_on_map`, `_remove_native_titlebar`, `_on_restore`)
- Corrigido `vault_entry_dialog.py` `_password_score` threshold de 8 → 12

### Infraestrutura
- Docker Compose com rede interna isolada
- Nginx como reverse proxy com TLS termination
- SQLite com WAL mode e índices otimizados
- Certificado self-signed (com bundle para clientes)

## [0.9.0] - 2026-03-31

### Adicionado (Infraestrutura Base)
- Auth server FastAPI com JWT (HS256) + refresh token rotation
- Password hashing com Argon2id
- Reuse detection em refresh tokens (revoga todos em caso de reutilização)
- Account lockout após tentativas falhadas de login
- Force password change (`must_change_password` column + endpoint)
- Rate limiting em Nginx (10r/s geral, 3r/min login/register)
- Security headers (HSTS, CSP, X-Frame-Options, X-Content-Type-Options)
- TLS 1.2/1.3 only com cipher suites modernos
- Docker multi-stage build com non-root user
- Containers read-only com no-new-privileges
- Resource limits (CPU + RAM) por container
- Healthchecks automáticos (Docker + Nginx)
- Backup automático SQLite cada 6h com integrity check
- Health monitor cada 5 min (containers, disco, endpoint, TLS)
- SSH hardening (password auth disabled, MaxAuthTries 3)
- Fail2ban com SSH jail (3 falhas = 2h ban)
- Auto-updates de segurança (unattended-upgrades)
- UFW firewall (deny default, allow 22/80/443)
- SSL verification com cert bundle (eliminou verify=False)
- Token cleanup automático (startup lifespan)
- Audit log completo (auth_events table)

### Segurança
- Credenciais Twilio removidas do config.json
- Secrets em .env com permissões 600
- /docs e /redoc bloqueados em produção
- Nginx headers: proxy_hide_header Server + X-Powered-By
- OCSP stapling desativado (incompatível com self-signed)
- Connection header corrigido para upstream keepalive

### Infraestrutura
- Docker Compose com rede interna isolada
- Nginx como reverse proxy com TLS termination
- SQLite com WAL mode e índices otimizados
- Certificado self-signed (com bundle para clientes)

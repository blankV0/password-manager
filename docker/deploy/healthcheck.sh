#!/usr/bin/env bash
# ═════════════════════════════════════════════════════════════════════════════
# deploy/healthcheck.sh — Verificação pós-deploy
# ─────────────────────────────────────────────────────────────────────────────
#
# Corre após "docker compose up -d" para confirmar que tudo está a funcionar.
#
# USO:
#   # Local (no servidor):
#   chmod +x deploy/healthcheck.sh
#   ./deploy/healthcheck.sh --host https://localhost
#
#   # Via Tailscale (na tua máquina):
#   ./deploy/healthcheck.sh --host https://meuservidor.tail1234.ts.net
#
# ═════════════════════════════════════════════════════════════════════════════

set -euo pipefail

# ─── Configuração ────────────────────────────────────────────────────────────
HOST="${1:-https://localhost}"
PASS=0
FAIL=0

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ok()   { echo -e "  ${GREEN}✓${NC} $1"; ((PASS++)); }
fail() { echo -e "  ${RED}✗${NC} $1"; ((FAIL++)); }
warn() { echo -e "  ${YELLOW}⚠${NC} $1"; }

echo ""
echo "════════════════════════════════════════════════════"
echo "  🏥  Health Check — Password Manager Auth Server"
echo "  Target: $HOST"
echo "════════════════════════════════════════════════════"
echo ""

# ─── Teste 1: Health endpoint ─────────────────────────────────────────────────
echo "[ 1/7 ] Health endpoint..."
HEALTH_RESP=$(curl -sk --max-time 5 "$HOST/health" 2>/dev/null || echo "ERROR")
if echo "$HEALTH_RESP" | grep -q '"ok":true'; then
    ok "GET /health → 200 {ok: true}"
else
    fail "GET /health → resposta inesperada: $HEALTH_RESP"
fi

# ─── Teste 2: HTTP → HTTPS redirect ──────────────────────────────────────────
echo "[ 2/7 ] HTTP → HTTPS redirect..."
HTTP_HOST=$(echo "$HOST" | sed 's/https:/http:/')
REDIRECT_CODE=$(curl -sk --max-time 5 -o /dev/null -w "%{http_code}" "$HTTP_HOST/health" 2>/dev/null || echo "0")
if [[ "$REDIRECT_CODE" == "301" ]]; then
    ok "GET http:// → 301 Redirect para HTTPS"
else
    warn "HTTP redirect retornou: $REDIRECT_CODE (pode ser normal se Nginx não está a correr na porta 80)"
fi

# ─── Teste 3: Certificado TLS ────────────────────────────────────────────────
echo "[ 3/7 ] Certificado TLS..."
HOSTNAME=$(echo "$HOST" | sed 's|https://||' | sed 's|/.*||')
CERT_INFO=$(echo | openssl s_client -connect "$HOSTNAME:443" -servername "$HOSTNAME" 2>/dev/null | openssl x509 -noout -dates 2>/dev/null || echo "ERROR")
if echo "$CERT_INFO" | grep -q "notAfter"; then
    EXPIRY=$(echo "$CERT_INFO" | grep "notAfter" | cut -d= -f2)
    ok "Certificado TLS válido — expira: $EXPIRY"
else
    warn "Não foi possível verificar o certificado TLS (pode ser self-signed ou Tailscale)"
fi

# ─── Teste 4: TLS versão mínima ──────────────────────────────────────────────
echo "[ 4/7 ] TLS version (deve rejeitar TLS 1.0 e 1.1)..."
TLS10=$(echo | openssl s_client -connect "$HOSTNAME:443" -tls1 2>&1 | grep -c "handshake failure\|alert\|no protocols" || true)
if [[ "$TLS10" -gt 0 ]]; then
    ok "TLS 1.0 rejeitado ✓"
else
    fail "TLS 1.0 pode estar habilitado — verificar ssl_protocols no nginx.conf"
fi

# ─── Teste 5: Security headers ───────────────────────────────────────────────
echo "[ 5/7 ] Security headers..."
HEADERS=$(curl -sk --max-time 5 -I "$HOST/health" 2>/dev/null || echo "ERROR")

if echo "$HEADERS" | grep -qi "strict-transport-security"; then
    ok "HSTS header presente"
else
    fail "HSTS header ausente — adicionar ao nginx.conf"
fi

if echo "$HEADERS" | grep -qi "x-content-type-options: nosniff"; then
    ok "X-Content-Type-Options: nosniff presente"
else
    fail "X-Content-Type-Options ausente"
fi

if echo "$HEADERS" | grep -qi "x-frame-options: deny"; then
    ok "X-Frame-Options: DENY presente"
else
    fail "X-Frame-Options ausente"
fi

if echo "$HEADERS" | grep -qi "content-security-policy"; then
    ok "Content-Security-Policy presente"
else
    fail "Content-Security-Policy ausente"
fi

# ─── Teste 6: /docs bloqueado ────────────────────────────────────────────────
echo "[ 6/7 ] /docs bloqueado em produção..."
DOCS_CODE=$(curl -sk --max-time 5 -o /dev/null -w "%{http_code}" "$HOST/docs" 2>/dev/null || echo "0")
if [[ "$DOCS_CODE" == "404" ]]; then
    ok "GET /docs → 404 (bloqueado em produção)"
else
    fail "GET /docs → $DOCS_CODE — deve ser 404 em produção"
fi

# ─── Teste 7: Auth register endpoint responde ────────────────────────────────
echo "[ 7/7 ] Auth register endpoint..."
REG_CODE=$(curl -sk --max-time 5 -o /dev/null -w "%{http_code}" \
    -X POST "$HOST/auth/register" \
    -H "Content-Type: application/json" \
    -d '{"email":"test@example.com","username":"testuser","password":""}' \
    2>/dev/null || echo "0")
if [[ "$REG_CODE" == "422" ]]; then
    ok "POST /auth/register → 422 (validação Pydantic a funcionar)"
elif [[ "$REG_CODE" == "429" ]]; then
    warn "POST /auth/register → 429 (rate limit ativo — OK, server a funcionar)"
else
    fail "POST /auth/register → $REG_CODE (esperado 422 ou 429)"
fi

# ─── Resumo ──────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════"
TOTAL=$((PASS + FAIL))
echo "  Resultado: ${PASS}/${TOTAL} testes passaram"
if [[ "$FAIL" -eq 0 ]]; then
    echo -e "  ${GREEN}🎉 Todos os testes passaram! Deployment OK.${NC}"
    exit 0
else
    echo -e "  ${RED}❌ ${FAIL} teste(s) falharam. Verificar configuração.${NC}"
    exit 1
fi
echo "════════════════════════════════════════════════════"
echo ""

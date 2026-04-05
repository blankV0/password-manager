Este directório contém os certificados TLS para o Nginx.

NUNCA commitar os certificados reais (.pem) no git.

Como obter o certificado:

─── OPÇÃO A: Tailscale (recomendado para servidor caseiro) ───────────────────

  1. Instalar Tailscale no servidor:
     curl -fsSL https://tailscale.com/install.sh | sh
     sudo tailscale up

  2. Ativar HTTPS no Tailscale (uma vez):
     No dashboard em https://login.tailscale.com/admin/dns
     → Ativar "HTTPS Certificates"

  3. Gerar certificado:
     sudo tailscale cert \
       --cert-file nginx/certs/fullchain.pem \
       --key-file  nginx/certs/privkey.pem \
       $(tailscale status --json | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['Self']['DNSName'].rstrip('.'))")

  4. Renovar (os certs Tailscale expiram após 90 dias — adicionar ao cron):
     0 0 1 * * sudo tailscale cert --cert-file /path/fullchain.pem --key-file /path/privkey.pem <hostname>

─── OPÇÃO B: Let's Encrypt (se tens domínio público) ─────────────────────────

  1. Instalar certbot:
     sudo apt install certbot

  2. Gerar certificado (servidor deve estar acessível na porta 80):
     sudo certbot certonly --standalone -d meuapp.duckdns.org

  3. Copiar para este directório:
     sudo cp /etc/letsencrypt/live/meuapp.duckdns.org/fullchain.pem nginx/certs/
     sudo cp /etc/letsencrypt/live/meuapp.duckdns.org/privkey.pem  nginx/certs/
     sudo chown $USER:$USER nginx/certs/*.pem

─── OPÇÃO C: Self-signed (apenas para testes locais) ─────────────────────────

  openssl req -x509 -nodes -days 365 -newkey rsa:4096 \
    -keyout nginx/certs/privkey.pem \
    -out    nginx/certs/fullchain.pem \
    -subj   "/CN=localhost/O=PasswordManager/C=PT"

  ⚠️  Browsers vão mostrar aviso de certificado não confiável.
  ⚠️  Não usar em produção.

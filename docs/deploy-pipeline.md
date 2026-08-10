# Deploy Pipeline (GitHub Actions → GHCR → Homelab)

Pipeline genérico para deploy automatizado de apps containerizadas com imagem no GitHub Container Registry.

## Arquitetura

```
GitHub Actions (no repo do app)
  ├── build + push imagem → ghcr.io/<owner>/<app>:<tag>
  └── curl deploy.<env>.batistela.tech/webhook/<app>
       │  └── HMAC-SHA256 (secret compartilhado)
       │
       ▼
tools VM: deploy-webhook.service (Python, porta 9999)
  ├── /opt/deploy/config.yml  ← lista de apps (Ansible)
  ├── /opt/deploy/.ghcr_token ← token read:packages (vault)
  └── /opt/deploy/<app>/docker-compose.yml
       │
       ├── docker login ghcr.io
       ├── docker compose pull
       └── docker compose up -d --force-recreate
```

## Como adicionar um novo app

### 1. No repo do app (GitHub)

Criar `.github/workflows/deploy.yml`:

```yaml
name: Build and Deploy
on:
  push:
    branches: [staging]

permissions:
  contents: read
  packages: write

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/metadata-action@v5
        id: meta
        with:
          images: ghcr.io/${{ github.repository }}
          tags: type=raw,value=staging,enable=${{ github.ref == 'refs/heads/staging' }}
      - uses: docker/build-push-action@v6
        with:
          push: true
          tags: ${{ steps.meta.outputs.tags }}
      - name: Trigger deploy
        if: github.ref == 'refs/heads/staging'
        env:
          PAYLOAD: '{}'
        run: |
          SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "${{ secrets.WEBHOOK_SECRET }}" | sed 's/^.* //')
          curl -sf -X POST "https://deploy.staging.batistela.tech/webhook/MY_APP" \
            -H "X-Hub-Signature-256: sha256=$SIGNATURE" \
            -d "$PAYLOAD"
```

**No repo do app, adicionar o secret:**
- `WEBHOOK_SECRET` — mesmo valor de `vault.tools.deploy_webhook_secret`

### 2. No repo `projects/homelab`

**a) Adicionar app em `ansible/inventories/local/host_vars/tools/deploy_apps.yml`:**

```yaml
deploy_webhook_apps:
  - name: my-app                    # usado na URL /webhook/my-app
    compose_dir: /opt/deploy/my-app # diretório com docker-compose.yml
    ghcr_image: ghcr.io/owner/my-app:staging
```

**b) Criar `docker-compose.yml` em `/opt/deploy/<app>/` na tools VM:**

```yaml
services:
  my-app:
    image: ghcr.io/owner/my-app:staging
    container_name: my-app
    restart: always
    ports:
      - "PORT:PORT"
```

**c) Expor o serviço (opcional):**

Criar service manifest em `config/services/tools/<app>.yml` + fragmentos Traefik/Pangolin conforme necessário.

**d) Aplicar:**

```bash
cd projects/homelab
make play-tools    # deploy webhook + docker-compose
make play-infra    # Traefik routes
make play-pangolin # public exposure
```

## Monitoramento

O webhook expõe métricas Prometheus em `/metrics`:

| Métrica | Descrição |
|---------|-----------|
| `deploy_webhook_uptime_seconds` | Tempo desde o start do serviço |
| `deploy_webhook_deploys_total{app}` | Total de deploys por app |
| `deploy_webhook_deploy_errors_total{app}` | Total de erros de deploy por app |
| `deploy_webhook_last_deploy_timestamp{app}` | Timestamp do último deploy |
| `deploy_webhook_unauthorized_total` | Tentativas com HMAC inválido |

O scrape config está em `ansible/inventories/local/host_vars/infra/prometheus_deploy_webhook.yml`.

## Segurança

- **Webhook**: HMAC-SHA256 com secret do vault (`vault.tools.deploy_webhook_secret`)
- **GHCR**: token `read:packages` armazenado no vault (`vault.tools.deploy_webhook_ghcr_token`)
- **Transporte**: HTTPS via Pangolin (Cloudflare → RackNerd → tunnel → Traefik)
- **Firewall**: webhook receiver binda em `0.0.0.0` mas só é exposto via Traefik/Pangolin

## Troubleshooting

```bash
# Ver logs do webhook
ssh tools journalctl -u deploy-webhook -f

# Ver logs de deploy de um app específico
ssh tools cat /var/log/<app>-deploy.log

# Testar webhook manualmente
WEBHOOK_SECRET=$(ansible-vault view ... | grep deploy_webhook_secret)
PAYLOAD='{}'
SIG=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$WEBHOOK_SECRET" | sed 's/^.* //')
curl -X POST "https://deploy.staging.batistela.tech/webhook/my-app" \
  -H "X-Hub-Signature-256: sha256=$SIG" -d "$PAYLOAD"
```

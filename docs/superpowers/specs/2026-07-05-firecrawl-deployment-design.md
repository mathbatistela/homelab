# Firecrawl Self-Host — Design (2026-07-05, final)

## Goal
Run Firecrawl (scrape/crawl/map/search API) self-hosted, **internal-only**, for Hermes/agents
to call at `http://firecrawl:3002`.

## Decisions
- **Dedicated `firecrawl` LXC** (192.168.1.112, vmid 112, **4c / 8G / 40G**) runs the whole
  self-contained stack: `api` + `playwright-service` + `nuq-postgres` + `redis`.
- **RabbitMQ** = new **shared** service (`rabbitmq:3-management`) on the `database` VM (own role,
  reusable), Firecrawl connects via `NUQ_RABBITMQ_URL`.
- **Images**: prebuilt `ghcr.io/firecrawl/{firecrawl,playwright-service,nuq-postgres}` + `redis:alpine`.
- **Search**: `SEARXNG_ENDPOINT=http://<tools>:8080` (the SearXNG already deployed).
- **Auth**: `USE_DB_AUTHENTICATION=false`, no Traefik/Pangolin exposure.
- **LLM extract**: off for now (add OpenRouter later via `OPENAI_BASE_URL`/`MODEL_NAME`).

### Why self-contained (not reusing shared Postgres/Redis)
- `nuq.sql` runs instance-wide `ALTER SYSTEM` re-tuning (max_wal_size 16GB, wal/checkpoint/bgwriter,
  `pg_cron` + cron jobs) — it is designed to **own** its Postgres instance; applying it to the shared
  DB would clobber the tuned `postgresql_global_config_options` and impact every other database.
- Shared Redis ACL users are managed out-of-band (not in IaC) and need the Redis admin cred (absent).
- → Bundle `nuq-postgres` + `redis` with Firecrawl; keep only RabbitMQ shared (it's a new service anyway).

## Architecture
```
Hermes ── HTTP :3002 ──► firecrawl VM (192.168.1.112)
                           ├─ api (ghcr.io/firecrawl/firecrawl)  :3002
                           ├─ playwright-service                 (compose-internal)
                           ├─ nuq-postgres (ghcr.io/firecrawl/nuq-postgres, pg_cron+nuq.sql at init)
                           ├─ redis:alpine                       (compose-internal)
                           ├─ RabbitMQ  → database:5672          (shared, new role)
                           └─ /search   → tools:8080 (SearXNG)
```

## Components / changes
1. **New VM** — `config/network.json` (`firecrawl: 192.168.1.112`), `terraform/home/main.tf`
   (`firecrawl` block, vmid 112, 4c/8192/40G), `ansible/inventories/local/hosts.yml`
   (add to `proxmox`, `docker_monitored`, `monitored_nodes`). Provider creates it stopped →
   `pct start 112`.
2. **`ansible/roles/firecrawl`** (new) — docker-compose with 4 services (prebuilt images). `api`
   publishes `3002` on `0.0.0.0`; `nuq-postgres` on a persistent volume with `POSTGRES_PASSWORD`
   from vault; `redis:alpine` internal. Env: `REDIS_URL=redis://redis:6379`,
   `REDIS_RATE_LIMIT_URL=redis://redis:6379`, `PLAYWRIGHT_MICROSERVICE_URL=http://playwright-service:3000/scrape`,
   `POSTGRES_HOST=nuq-postgres POSTGRES_PORT=5432 POSTGRES_USER=postgres POSTGRES_DB=postgres
   POSTGRES_PASSWORD=<vault>`, `NUQ_RABBITMQ_URL=amqp://<user>:<pw>@<database>:5672`,
   `USE_DB_AUTHENTICATION=false`, `HOST=0.0.0.0`, `PORT=3002`, `SEARXNG_ENDPOINT=http://<tools>:8080`.
3. **`ansible/playbooks/vms/firecrawl.yml`** (new) — roles: `geerlingguy.docker`, `firecrawl`.
4. **`ansible/roles/rabbitmq`** (new) on `database` — `rabbitmq:3-management`, ports 5672 + 15672
   (mgmt UI), persistent volume, `RABBITMQ_DEFAULT_USER/PASS` from vault. Add to
   `ansible/playbooks/vms/database.yml`.
5. **Manifest** `config/services/firecrawl/firecrawl.yml` — internal (both exposures disabled),
   `owner: role`, port 3002. (Optional 2nd manifest for RabbitMQ mgmt UI if you want it exposed later.)
6. **Vault** — `vault.firecrawl.nuq_postgres_pw`, `vault.database.rabbitmq_admin_pw` (Firecrawl's
   `NUQ_RABBITMQ_URL` uses the admin user for now; dedicated per-service user later). Redis bundled, no auth.

## Verification
- `database`: `docker ps` shows `rabbitmq` healthy; mgmt UI reachable on `:15672`.
- `firecrawl` VM: 4 containers up (api/playwright/nuq-postgres/redis); `nuq-postgres` has `pg_cron` +
  `nuq` schema; API responds on `:3002`.
- End-to-end from `hermes`: `POST http://firecrawl:3002/v1/scrape {"url":"https://example.com"}` →
  content; `POST /v1/search {"query":"..."}` → SearXNG-backed results.

## Rollback
- Remove `firecrawl` from Terraform + `pct destroy 112`; the shared RabbitMQ is independent (keep/remove).
- Nothing touched on the shared `database` Postgres/Redis, so no shared-service risk.

## Deferred
- LLM extract via OpenRouter; dedicated RabbitMQ vhost/user per service; expose Firecrawl/RabbitMQ UI via SSO if ever needed.

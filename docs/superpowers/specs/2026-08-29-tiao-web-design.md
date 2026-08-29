# Tião Web — Caderneta viewer (2026-08-29)

## Goal

Give Seu Jader (a cattle rancher, non-technical, Portuguese-only) a way to *look at* the
ledger data the Tião bot records for him — from his phone, at the ranch — without ever
seeing a URL parameter, a login form, or anything technical.

Reachable at `https://tiao.batistela.tech`, PIN-gated at the Pangolin edge, serving four
named views plus arbitrary ad-hoc views the bot composes on demand. Every page looks the
same regardless of subject.

## Decisions

- **The AI emits a *view spec* (JSON), never HTML or CSS.** A fixed server-side renderer
  turns any spec into a page. This is the load-bearing decision — see "Why" below.
- **Named views are saved specs, not separate code paths.** `/pesagens`, `/animal/<brinco>`,
  `/rebanho`, `/negocios` and `/v/<token>` all render through the same component set.
- **Live data by default.** A page re-runs its query on open, so opening it right after a
  weighing shows what Tião just recorded — the moment a misread ear-tag is still catchable.
  A spec may set `"congelado": true` to freeze a snapshot instead.
- **Dedicated read-only Postgres role** `tiao_web_user` (`SELECT` only, `statement_timeout`,
  `default_transaction_read_only`). The web layer physically cannot damage the ledger.
- **Server-rendered HTML, zero JS build, charts as server-generated inline SVG.** No CDN, no
  bundler. Ranch connectivity is poor; a page that depends on a CDN fails exactly where it
  is needed.
- **No auth in the app.** Pangolin's `pincode` authenticates at the edge, before the request
  reaches the VM. We write no session, cookie, or password code.
- **Two listeners, separated by Docker port publishing.** Read routes on **8790**, published on
  the LAN IP for Pangolin. Spec creation (`POST /specs`) on **8791**, published on `127.0.0.1`
  only, where the natively-running Tião can reach it. Docker enforces the boundary, so there is
  no shared secret to leak or rotate.
- **Built as a repo app** under `apps/tiao-web/` following the existing framework (`app.yml`,
  Dockerfile, CI to GHCR), deployed to the `hermes` VM (192.168.1.111) by a `tiao_web` Ansible
  role that mirrors `hermes_tools`.
- **UI copy is Portuguese only**, with no technical vocabulary — the `SOUL.md` rule ("nunca
  mostre comando, código, terminal, SQL nem nada técnico") extends to the interface.

### Why the view-spec indirection

The request was "AI-generated tables, always following the same pattern". Those pull apart:
if the model authors HTML, the layout drifts every time, which is the confusion we are trying
to avoid. Splitting the responsibility resolves it — **the AI decides *what* to show, the
template decides *how* it looks**:

- *Consistency* is guaranteed by construction, not by the model's discipline. Two pages on
  unrelated subjects are visually identical because they share one stylesheet and one set of
  components.
- *Testability*: the renderer can be tested against fixed specs with no model in the loop, and
  the queries tested against a seeded database. Had the model emitted HTML, every output would
  be unique and there would be nothing stable to assert.
- *Maintenance*: restyling later means editing one stylesheet, not N generated pages.

## Architecture

```
  Seu Jader (celular, fazenda)
        │  https://tiao.batistela.tech        PIN checked HERE
        ▼
  Pangolin / Traefik  (racknerd VPS, *.batistela.tech wildcard → this box)
        │  http → 192.168.1.111:8790          LAN only; never public
        ▼
  tiao-web container  (hermes VM, docker compose)
        ├── :8790 published on 192.168.1.111 — read routes
        ├── :8791 published on 127.0.0.1     — POST /specs ◄── Tião (native, same VM)
        ├── renderer: spec JSON ──► HTML (Jinja) + inline SVG chart
        └── spec store: /var/lib/tiao-web/specs/<token>.json  (TTL, bind mount)
        │
        ▼  SELECT only, 5s timeout
  postgres @ 192.168.1.103  tiao_database  (as tiao_web_user)
        ▲
        └── writes come only from the Tião bot, as tiao_user
```

## The view spec

The contract between the bot and the renderer. Deliberately small:

```jsonc
{
  "titulo": "Pesagem de 21/06/2026",
  "resumo":  [ {"rotulo": "Cabeças", "valor": "17"},
               {"rotulo": "Média",   "valor": "291 kg"} ],
  "fonte": {
    "sql":    "SELECT a.brinco, p.peso_kg FROM pesagens p JOIN animais a ON a.id = p.animal_id WHERE p.data = :data",
    "params": { "data": "2026-06-21" }
  },
  "tabela": {
    "colunas": [ {"campo": "brinco",  "rotulo": "Brinco"},
                 {"campo": "peso_kg", "rotulo": "Peso", "formato": "kg"} ],
    "ordenar": "peso_kg desc"
  },
  "grafico":  { "tipo": "barras", "x": "brinco", "y": "peso_kg" },
  "filtros":  [ {"campo": "categoria", "rotulo": "Categoria", "tipo": "select"} ],
  "validade": "24h",
  "congelado": false
}
```

Only `titulo`, `fonte` and `tabela` are required. `formato` is one of `kg`, `reais`, `data`,
`texto` — formatting lives in the component, so a weight renders identically on every screen.

**Validation on ingest** (`POST /specs`) and again before execution:

1. The statement must parse as a single `SELECT`. Reject multiple statements, CTEs that write,
   and any DML/DDL keyword.
2. Every `:name` in the SQL must be present in `params`, and vice versa. Values are **bound by
   the driver**, never interpolated — so the filters Seu Jader clicks can never become SQL.
3. A `LIMIT` is appended if absent (cap 500 rows).
4. `statement_timeout` is enforced by the role itself, so even a pathological query dies on its own.

## Views and URLs

| URL | screen | source |
|---|---|---|
| `/` | home: large shortcuts + latest weighings | named spec |
| `/pesagens?data=` | the day's weighing, with summary | named spec |
| `/animal/<brinco>` | one animal's weight history + trend chart | named spec |
| `/rebanho?categoria=` | whole herd, filterable | named spec |
| `/negocios?tipo=` | purchases and sales, per-head value | named spec |
| `/v/<token>` | ad-hoc view the bot composed | stored spec |
| `/saude` | healthcheck for Pangolin | — |

## Tião's role

The bot gains one capability alongside the existing `tiao-gado` skill: handing over a link.

- **Common question** ("me mostra a pesagem de ontem") → build the named URL directly. No model
  round-trip, instant.
- **Off-pattern question** ("quais novilhas passaram de 300 em junho") → compose a spec,
  `POST /specs` on localhost, receive a token, send `/v/<token>`.
- **Delivery follows SOUL.md**: *"Tá tudo aqui ó, patrão: tiao.batistela.tech/..."* — never
  explaining a URL, token, or filter.

## Postgres

New read-only role on the `database` host (192.168.1.103):

```sql
CREATE USER tiao_web_user PASSWORD '...';
GRANT CONNECT ON DATABASE tiao_database TO tiao_web_user;
GRANT USAGE  ON SCHEMA public TO tiao_web_user;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO tiao_web_user;
ALTER DEFAULT PRIVILEGES FOR ROLE tiao_user IN SCHEMA public
  GRANT SELECT ON TABLES TO tiao_web_user;
ALTER ROLE tiao_web_user SET statement_timeout = '5s';
ALTER ROLE tiao_web_user SET default_transaction_read_only = on;
```

`ALTER DEFAULT PRIVILEGES` matters: without it any table created later is invisible to the web
layer, and the symptom surfaces weeks later as "a screen disappeared".

### Drift to fix in the same change

`tiao_user` / `tiao_database` were created by hand and are **absent** from
`ansible/inventories/local/host_vars/database/postgresql_databases.yml`. Bring both under
Ansible in this change, storing **the current password** in the vault as
`vault.database.tiao_user_pw`.

> Adding an existing user to `postgresql_users` with a *new* vault password rewrites that
> password, and the bot would lose the database on the next `make play-database` — surfacing
> only as Tião saying "deu ruim, patrão". The vault value must be a copy of the live password.

## App and deployment

The app follows the repo's existing framework (`apps/README.md`), so it appears in
`homelab-apps list`, is validated by `homelab-apps validate`, and is built by CI to GHCR:

```
apps/tiao-web/
├── app.yml               # host: hermes, public exposure, healthcheck /saude
├── Dockerfile            # python:3.11-slim, single service
├── README.md
└── src/tiao_web/         # sql_guard.py, spec.py, chart.py, render.py, db.py, views.py, app.py
    └── templates/        # base.html.j2, pagina.html.j2, estilo.css
```

Deployment mirrors `ansible/roles/hermes_tools/` exactly — the established pattern on this repo:

```
ansible/roles/tiao_web/
├── defaults/main.yml                 # ports, image, compose dir, db host
├── tasks/main.yml                    # compose dir → GHCR login → template → docker_compose_v2
└── templates/
    ├── docker-compose.yml.j2         # the two port publishes; /var/lib/tiao-web bind mount
    └── env.j2                        # PG* for tiao_web_user (from vault)
```

Added to `ansible/playbooks/vms/hermes.yml`; deployed with `make play-hermes`.

**Prerequisite:** `hermes_tools` pulls from GHCR using `deploy_webhook_ghcr_token` out of
`host_vars/tools/deploy_apps.yml`. The `hermes` host has no equivalent yet, so this change adds
GHCR pull credentials for it. Docker itself is already present and in use on that VM.

Spec files live in `/var/lib/tiao-web` on the host, bind-mounted into the container —
deliberately outside `~/.hermes/profiles/tiao/`, so redeploying the service never risks the
bot's own profile state.

## Pangolin

`config/fragments/pangolin/tiao.yml` — auto-discovered by the `fileglob` in
`ansible/playbooks/vms/pangolin.yml`; no registration needed.

```yaml
pangolin_fragment_resources:
  tiao:
    name: Tião — Caderneta
    protocol: http
    full-domain: "tiao.{{ pangolin_base_domain }}"
    auth:
      pincode: 240810
    targets:
      - site: "{{ pangolin_site_nice_id }}"
        hostname: "{{ hostvars['hermes'].ansible_host }}"
        port: 8790
        method: http
        healthcheck:
          hostname: "{{ hostvars['hermes'].ansible_host }}"
          port: 8790
          enabled: true
          path: /saude
          scheme: http
          interval: 5
```

**No DNS change**: `terraform/cloud/dns.tf` already publishes a `*` A record for the zone
pointing at the Pangolin host, so `tiao.batistela.tech` resolves today.

The PIN is written literally, matching the existing `wedding-rsvp.yml` precedent. A
`{{ vault.* }}` reference was considered and rejected: `make play-pangolin` loads **both** the
local and cloud inventories, each with its own encrypted `group_vars/all/vault.yml`, and with
Ansible's default `replace` hash behaviour a top-level `vault` key in one silently shadows the
other. The PIN gates a private page containing only this family's own data; the collision risk
outweighs the benefit.

## Security model

| Layer | Control |
|---|---|
| Edge | Pangolin `pincode`; TLS terminates on the VPS |
| Network | 8790 published on the LAN IP only; the internet arrives through the tunnel |
| Write path | 8791 published on `127.0.0.1` only, enforced by Docker |
| SQL | single-`SELECT` check, bound parameters, forced `LIMIT` |
| Database | `tiao_web_user` has `SELECT` only, read-only transactions, 5s timeout |

The layers are independent: model-authored SQL is contained by database privileges, and
Seu Jader's filter clicks are contained by parameter binding, regardless of the SQL.

## Testing

- **Renderer** — golden tests: fixed specs in, stable HTML out. Deterministic, no model in the
  loop, so it catches visual regressions.
- **SQL guard** — `INSERT`/`UPDATE`/`DROP`/multi-statement inputs are rejected; parameters are
  bound rather than interpolated.
- **Queries** — the four named views run against a seeded database with asserted numbers.
- **End-to-end** — `curl https://tiao.batistela.tech` returns 401 without the PIN, 200 with it.
- **Real** — open it on a phone. The only test that says whether it works *for Seu Jader*.

## Phasing

1. **Infrastructure end to end with one real screen** — role, service, read-only user, Pangolin
   fragment, PIN, plus `/pesagens`. Proves every layer with the screen that best guards against
   a misread ear-tag.
2. **The remaining named views** — `/animal/<brinco>`, `/rebanho`, `/negocios`, `/`. Same
   renderer, so these are specs and queries, not new machinery.
3. **Ad-hoc specs** — `POST /specs`, `/v/<token>`, TTL sweep, and the bot-side link skill.

## Notes

The PIN (`240810`) is committed literally in the fragment, per the reasoning above. It is an
access PIN for a private page of the family's own records, not a credential to any system — but
it does enter git history, so rotating it means a new commit, not a secret-store update.

# tiddl-manager

CLI para gerenciar assinaturas de playlists/álbuns/artistas do Tidal e sincronizar
automaticamente com o Navidrome. Complementa o [tiddl](https://github.com/oskvr37/tiddl)
adicionando controle de estado, download incremental e orquestração cron-friendly.

## Arquitetura

```
                     ┌────────────────────────┐
                     │   tiddl-manager CLI     │
                     │  (Docker, FROM tiddl)   │
                     └───────────┬────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
     ┌────────────┐   ┌──────────────┐   ┌──────────────────┐
     │ Tidal API  │   │  tiddl CLI   │   │  SQLite state    │
     │ (metadata) │   │  (download)  │   │ .tiddl-manager/  │
     └────────────┘   └──────┬───────┘   └──────────────────┘
                             │
                    ┌────────▼────────┐
                    │  /downloads/    │
                    │  ├── matheus/   │
                    │  ├── pamella/   │
                    │  ├── yoko/      │
                    │  └── shared/    │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │   Navidrome     │
                    │   (:4533)       │
                    └─────────────────┘
```

- **tiddl-manager** cuida do _que_ baixar (assinaturas, tracking de faixas já baixadas)
- **tiddl** cuida do _como_ (auth, download, ffmpeg, qualidade)
- **Navidrome** serve o resultado final via Subsonic API

## Instalação

### Pré-requisitos

- Docker (tiddl-manager roda como container)
- `tiddl:3.4.4` built localmente (imagem base)
- Auth do Tidal configurada (`tiddl auth login`)

### Build

```bash
cd apps/tiddl-manager
docker build -t tiddl-manager:latest .
```

### CI/CD

Push na branch `main` com mudanças em `apps/tiddl-manager/**` dispara o workflow
`.github/workflows/build-tiddl-manager.yml`. Ele builda a imagem `tiddl:3.4.4`
do repo upstream, builda o tiddl-manager e pusha para `ghcr.io/mathbatistela/tiddl-manager:latest`.

### Wrapper script (na VM media)

```bash
cat > /usr/local/bin/tiddl-manager << 'SCRIPT'
#!/bin/bash
exec docker run --rm \
  -v tiddl_config:/root/.tiddl \
  -v tiddl_manager_state:/root/.tiddl-manager \
  -v /mnt/homeshare/data/media/music:/downloads \
  tiddl-manager:latest "$@"
SCRIPT
chmod +x /usr/local/bin/tiddl-manager
```

**Volumes:**
| Volume | Container path | Conteúdo |
|--------|---------------|----------|
| `tiddl_config` | `/root/.tiddl` | auth.json do Tidal (compartilhado com tiddl) |
| `tiddl_manager_state` | `/root/.tiddl-manager` | SQLite DB com subscriptions e tracking |
| bind mount | `/downloads` | Destino dos downloads (mesmo path do tiddl) |

## Comandos

### subscribe

Assina uma playlist, álbum ou artista para sincronização automática.

```bash
# Por URL completa do Tidal
tiddl-manager subscribe https://tidal.com/browse/playlist/uuid-abc123 --user matheus

# Por resource/id
tiddl-manager subscribe playlist/uuid-abc123 --user pamella

# Com nome customizado (útil para playlists com nomes genéricos)
tiddl-manager subscribe album/123456 -u matheus -n "Álbum favorito"

# Artista (baixa top 50 tracks no sync)
tiddl-manager subscribe artist/98765 -u shared
```

**Tipos suportados:** `playlist`, `album`, `artist`

O nome é automaticamente resolvido via Tidal API. Use `--name` / `-n` para
sobrescrever.

### list

Lista todas as assinaturas ativas.

```bash
# Todas
tiddl-manager list

# Filtrado por usuário
tiddl-manager list --user matheus
```

Output:
```
ID                                       Type       User       Name                           Last Sync            Tracks
─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
uuid-abc123                              playlist   matheus    My Playlist                    2026-07-29T04:00:00      42
album-456                               album      pamella    Álbum Teste                    -                         0
```

### unsubscribe

Remove uma assinatura (não deleta os arquivos já baixados).

```bash
tiddl-manager unsubscribe uuid-abc123
```

### sync

Sincroniza as assinaturas — baixa apenas faixas novas.

```bash
# Todas as assinaturas
tiddl-manager sync

# Apenas um usuário
tiddl-manager sync --user matheus
```

O sync é **incremental**: compara cada faixa contra a tabela `downloaded_tracks`
e só chama o tiddl para faixas nunca baixadas antes. Faixas já baixadas são
puladas automaticamente.

Output:
```
Syncing all users...
  ✓ My Playlist (matheus): 3 new, 39 skipped
  ✓ Álbum Teste (pamella): 10 new, 0 skipped

Total: 13 downloaded, 39 skipped
```

### download

Download one-shot (não cria assinatura, não trackeia).

```bash
tiddl-manager download track/103805726 --user matheus
tiddl-manager download album/12345 --user shared
tiddl-manager download https://tidal.com/browse/playlist/uuid-xyz -u yoko
```

Útil para baixar algo pontual sem criar assinatura. Usa o tiddl diretamente
(4 threads para playlists, qualidade max).

### history

Mostra o histórico de sync de uma assinatura.

```bash
tiddl-manager history uuid-abc123
tiddl-manager history uuid-abc123 --limit 20
```

Output:
```
Sync history for 'My Playlist' (matheus):
Date                 Status     New   Skipped   Error
────────────────────────────────────────────────────
2026-07-29T04:00:00  done          3        39
2026-07-28T04:00:00  done          0        42
2026-07-27T04:00:00  failed        0         0   Rate limit
```

## Cron setup

Sync diário automático das assinaturas. Na VM `media`:

```bash
cat > /etc/cron.d/tiddl-manager << 'CRON'
# Daily sync of Tidal subscriptions at 4am
0 4 * * * root /usr/local/bin/tiddl-manager sync >> /var/log/tiddl-manager.log 2>&1
CRON

systemctl restart cron
```

**Log:** `/var/log/tiddl-manager.log`

**Por que 4am?** É o mesmo horário dos scans do Navidrome (a cada 6h a partir
de 4am). As músicas novas baixadas às 4am aparecem na biblioteca no scan seguinte.

### Verificar se o cron rodou

```bash
tail -20 /var/log/tiddl-manager.log
tiddl-manager history <subscription-id>
```

## Estrutura do banco de dados

SQLite em `/root/.tiddl-manager/tiddl-manager.db` (dentro do volume
`tiddl_manager_state`). Três tabelas:

- **subscriptions** — playlists/álbuns/artistas assinados por usuário
- **downloaded_tracks** — faixas já baixadas (id + subscription_id = chave composta), evita re-download
- **sync_runs** — log de cada execução de sync (status, faixas novas, erros)

## Troubleshooting

### `Auth file not found. Run 'tiddl auth login' first.`

O volume `tiddl_config` não tem `auth.json` ou não está montado. Verifique:

```bash
docker run --rm -v tiddl_config:/root/.tiddl alpine cat /root/.tiddl/auth.json
```

Se vazio, faça auth primeiro:

```bash
nohup tiddl auth login > /tmp/tiddl_auth.log 2>&1 &
cat /tmp/tiddl_auth.log  # pega o link https://link.tidal.com/XXXXX
```

### `tiddl not found`

O container do tiddl-manager não tem o binário `tiddl` no PATH. Isso não deve
acontecer porque o Dockerfile usa `FROM tiddl:3.4.4`, que inclui o tiddl CLI.
Se acontecer, verifique se a imagem base foi buildada corretamente:

```bash
docker run --rm tiddl:3.4.4 tiddl --version
```

### State não persiste entre execuções

O volume `tiddl_manager_state` precisa ser o mesmo em todas as chamadas.
Verifique se o wrapper script monta o volume:

```bash
docker volume inspect tiddl_manager_state
# Deve retornar Mountpoint e metadados
```

Se o volume não existe:

```bash
docker volume create tiddl_manager_state
```

### Tidal API rate limit / 429

A API do Tidal tem rate limiting. Se encontrar erros 429 durante o sync, o
cliente usa `requests-cache` com cache em `/root/.tiddl/api_cache.sqlite`,
o que reduz chamadas repetidas. Em caso de rate limit persistente, rode o sync
com menos assinaturas de uma vez ou espace os intervalos.

### `subscription_id` mostrado no history é o UUID do Tidal

O ID que aparece no `list` e que você usa no `unsubscribe` e `history` é o UUID
do recurso no Tidal, **não** um ID gerado pelo tiddl-manager. Isso facilita
correlacionar com URLs do Tidal.

### Download timeout após 300s (5 min) por faixa

Faixas individuais têm timeout de 300s; playlists (download one-shot) têm 3600s
(1h). Se faixas consistentemente timeout, verifique a conectividade com os
servidores do Tidal.

### Navidrome não enxerga as músicas novas

O Navidrome faz scan a cada 6h. Se você baixou músicas novas e quer vê-las
imediatamente, dispare um scan manual na UI do Navidrome (Settings → Scan) ou:

```bash
curl -sk -X GET "https://music.local.batistela.tech/api/library/scan" \
  -H "X-ND-Authorization: Bearer $TOKEN"
```

## Workflow típico

1. **Auth:** `tiddl auth login` (uma vez)
2. **Assinar:** `tiddl-manager subscribe playlist/ID -u matheus` (para cada playlist)
3. **Conferir:** `tiddl-manager list`
4. **Primeiro sync:** `tiddl-manager sync` (baixa tudo)
5. **Cron:** Configurar sync diário às 4am
6. **Manutenção:** `tiddl-manager list` / `tiddl-manager history ID` para monitorar

## Como contribuir

Estrutura do projeto:

```
apps/tiddl-manager/
├── Dockerfile              # Build FROM tiddl:3.4.4
├── pyproject.toml          # typer + requests + requests-cache
├── README.md
├── src/tiddl_manager/
│   ├── __init__.py
│   ├── cli.py              # Comandos Typer
│   ├── db.py               # Conexão SQLite + migrações
│   ├── state.py            # CRUD de subscriptions
│   ├── sync.py             # Lógica de sync incremental
│   ├── downloader.py       # Wrapper do tiddl CLI
│   └── tidal_api.py        # Tidal API client com cache
└── tests/
    └── (adicionar)
```

### Rodar localmente (sem Docker)

```bash
cd apps/tiddl-manager
pip install -e .
tiddl-manager --help
```

Nota: os comandos `sync` e `download` dependem do binário `tiddl` no PATH
e de `/downloads/` existente. Para desenvolvimento, use o Docker.

## Dependências

- **tiddl** (imagem base, v3.4.4): auth Tidal + download + ffmpeg
- **typer**: CLI framework
- **requests** + **requests-cache**: Tidal API com cache HTTP
- **SQLite**: state tracking (WAL mode, foreign keys enabled)
- **Navidrome**: servidor de música (via Subsonic API, independente)

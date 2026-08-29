# tiao-web

Read-only viewer for the Tião bot's cattle ledger (`tiao_database`).

Renders *view specs* — JSON describing a title, a `SELECT` with bound parameters, a table and
an optional chart — through one fixed template, so every page looks the same.

- `8790` read routes, reached through Pangolin at `https://tiao.batistela.tech` (PIN-gated)
- `8791` `POST /specs`, bound to `127.0.0.1`, for the bot on the same VM — **not built yet.**
  Phase 1 ships read routes only. When it arrives it has to be a *second* ASGI app or a second
  process: a `POST /specs` route added to this app would be served on 8790 as well, i.e.
  through Pangolin behind only the PIN, which is not the boundary the design describes.

Run the tests: `cd apps/tiao-web && uv run pytest` (or `pytest` in a venv with the dev group).

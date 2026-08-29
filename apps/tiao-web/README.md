# tiao-web

Read-only viewer for the Tião bot's cattle ledger (`tiao_database`).

Renders *view specs* — JSON describing a title, a `SELECT` with bound parameters, a table and
an optional chart — through one fixed template, so every page looks the same.

- `8790` read routes, reached through Pangolin at `https://tiao.batistela.tech` (PIN-gated)
- `8791` `POST /specs`, bound to `127.0.0.1`, used by the bot on the same VM

Run the tests: `cd apps/tiao-web && uv run pytest` (or `pytest` in a venv with the dev group).

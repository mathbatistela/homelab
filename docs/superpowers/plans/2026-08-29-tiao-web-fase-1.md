# Tião Web — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the full stack end-to-end with one real screen — `https://tiao.batistela.tech/pesagens` showing the day's weighing, PIN-gated, reading live from Postgres as a read-only role.

**Architecture:** A Python app renders any *view spec* (JSON: title, SQL + bound params, table, optional chart) into HTML through one fixed template. Named views are stored specs, so screens are data, not code. It runs as a Docker container on the `hermes` VM, publishing read routes on the LAN for Pangolin and the write route on `127.0.0.1` for the bot.

**Tech Stack:** Python 3.11, Starlette, Jinja2, SQLAlchemy 2.x (`text()` gives real `:name` binding), psycopg 3, sqlparse, pytest. Docker + GHCR + Ansible for delivery.

**Spec:** `docs/superpowers/specs/2026-08-29-tiao-web-design.md`

## Global Constraints

- **All UI copy is Portuguese, with no technical vocabulary.** No "id", "query", "null", "erro 500". This extends the Tião `SOUL.md` rule to the interface.
- **The web layer never writes.** All database access is as `tiao_web_user` (`SELECT` only, `default_transaction_read_only = on`, `statement_timeout = '5s'`).
- **No JS build, no CDN.** Server-rendered HTML; charts are server-generated inline SVG. Ranch connectivity is poor.
- **Row cap: 500.** A `LIMIT` is appended when the spec's SQL lacks one.
- **Ports: 8790** read routes (published on the LAN IP), **8791** `POST /specs` (published on `127.0.0.1` only).
- **Python 3.11** (matches the `hermes` VM).
- Repo app conventions live in `apps/README.md`; the deployment role mirrors `ansible/roles/hermes_tools/`.

---

### Task 1: Scaffold the app and the SQL guard

The guard is the security boundary for model-authored SQL. Scaffolding folds in here because this is the first task that needs a package to live in.

**Files:**
- Create: `apps/tiao-web/app.yml`
- Create: `apps/tiao-web/pyproject.toml`
- Create: `apps/tiao-web/README.md`
- Create: `apps/tiao-web/src/tiao_web/__init__.py`
- Create: `apps/tiao-web/src/tiao_web/sql_guard.py`
- Test: `apps/tiao-web/tests/test_sql_guard.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `sql_guard.check_sql(sql: str, *, limite: int = 500) -> str` — returns the SQL with a `LIMIT` appended when absent; raises `sql_guard.SqlNaoPermitido(str)` otherwise.

- [ ] **Step 1: Create the app scaffold**

`apps/tiao-web/app.yml`:

```yaml
app:
  name: tiao-web
  description: Caderneta do gado do Seu Jader — visualização em tabelas e gráficos
  version: 0.1.0

  services:
    app:
      type: backend
      port: 8790
      image:
        name: tiao-web
        tag: latest
      healthcheck:
        path: /saude
        interval: 30s

  homelab:
    host: hermes
    category: productivity

    exposure:
      local:
        enabled: false
        subdomain: tiao
      public:
        enabled: true
        subdomain: tiao

    resources:
      memory: 256M
      cpus: 0.25
```

`apps/tiao-web/pyproject.toml`:

```toml
[build-system]
requires = ["setuptools", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "tiao-web"
version = "0.1.0"
description = "Caderneta viewer for the Tiao bot"
requires-python = ">=3.11"
dependencies = [
    "starlette>=0.40",
    "uvicorn>=0.32",
    "jinja2>=3.1",
    "sqlalchemy>=2.0",
    "psycopg[binary]>=3.1",
    "sqlparse>=0.5",
]

[dependency-groups]
dev = ["pytest>=8.0", "httpx>=0.27"]

[tool.setuptools.packages.find]
where = ["src"]
```

`apps/tiao-web/README.md`:

```markdown
# tiao-web

Read-only viewer for the Tião bot's cattle ledger (`tiao_database`).

Renders *view specs* — JSON describing a title, a `SELECT` with bound parameters, a table and
an optional chart — through one fixed template, so every page looks the same.

- `8790` read routes, reached through Pangolin at `https://tiao.batistela.tech` (PIN-gated)
- `8791` `POST /specs`, bound to `127.0.0.1`, used by the bot on the same VM

Run the tests: `cd apps/tiao-web && uv run pytest` (or `pytest` in a venv with the dev group).
```

`apps/tiao-web/src/tiao_web/__init__.py`: empty file.

- [ ] **Step 2: Write the failing test**

`apps/tiao-web/tests/test_sql_guard.py`:

```python
import pytest

from tiao_web.sql_guard import SqlNaoPermitido, check_sql


def test_select_simples_passa_e_ganha_limit():
    assert check_sql("SELECT brinco FROM animais") == "SELECT brinco FROM animais LIMIT 500"


def test_limit_existente_e_preservado():
    sql = "SELECT brinco FROM animais LIMIT 10"
    assert check_sql(sql) == sql


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO animais (brinco) VALUES ('1')",
        "UPDATE animais SET brinco = '1'",
        "DELETE FROM animais",
        "DROP TABLE animais",
        "ALTER TABLE animais ADD COLUMN x TEXT",
        "TRUNCATE animais",
        "GRANT SELECT ON animais TO x",
    ],
)
def test_escrita_e_rejeitada(sql):
    with pytest.raises(SqlNaoPermitido):
        check_sql(sql)


def test_multiplas_instrucoes_sao_rejeitadas():
    with pytest.raises(SqlNaoPermitido):
        check_sql("SELECT 1; DROP TABLE animais")


def test_cte_que_escreve_e_rejeitada():
    with pytest.raises(SqlNaoPermitido):
        check_sql("WITH x AS (DELETE FROM animais RETURNING id) SELECT * FROM x")


def test_ponto_e_virgula_final_e_aceito():
    assert check_sql("SELECT 1;") == "SELECT 1 LIMIT 500"
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd apps/tiao-web && python -m pytest tests/test_sql_guard.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tiao_web.sql_guard'`

- [ ] **Step 4: Write the implementation**

`apps/tiao-web/src/tiao_web/sql_guard.py`:

```python
"""Guard for model-authored SQL.

The bot writes the SELECT in a view spec, so this is the boundary that keeps a
generated statement from doing anything but reading. It is one of three
independent layers: the database role is SELECT-only and read-only, and every
value the user picks is bound rather than interpolated.
"""

import sqlparse

PROIBIDAS = {
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE",
    "GRANT", "REVOKE", "COPY", "CALL", "DO", "MERGE", "REFRESH", "VACUUM",
}


class SqlNaoPermitido(Exception):
    """The statement is not a plain single SELECT."""


def check_sql(sql: str, *, limite: int = 500) -> str:
    texto = (sql or "").strip().rstrip(";").strip()
    if not texto:
        raise SqlNaoPermitido("consulta vazia")

    instrucoes = [s for s in sqlparse.split(texto) if s.strip()]
    if len(instrucoes) != 1:
        raise SqlNaoPermitido("apenas uma consulta por vez")

    analisada = sqlparse.parse(texto)[0]
    if (analisada.get_type() or "").upper() != "SELECT":
        raise SqlNaoPermitido("apenas SELECT e permitido")

    # Defence in depth: get_type() reports SELECT for a CTE whose inner
    # statement writes, so scan every keyword token too.
    for token in analisada.flatten():
        if token.ttype in sqlparse.tokens.Keyword and token.normalized.upper() in PROIBIDAS:
            raise SqlNaoPermitido(f"comando nao permitido: {token.normalized}")
        if token.ttype is sqlparse.tokens.Keyword.DML and token.normalized.upper() != "SELECT":
            raise SqlNaoPermitido(f"comando nao permitido: {token.normalized}")

    if not _tem_limit(analisada):
        texto = f"{texto} LIMIT {limite}"
    return texto


def _tem_limit(analisada) -> bool:
    return any(
        token.ttype in sqlparse.tokens.Keyword and token.normalized.upper() == "LIMIT"
        for token in analisada.flatten()
    )
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd apps/tiao-web && python -m pytest tests/test_sql_guard.py -v`
Expected: PASS — 11 passed

- [ ] **Step 6: Validate the app manifest**

Run: `./scripts/homelab-apps validate`
Expected: `tiao-web` validates with no errors.

- [ ] **Step 7: Commit**

```bash
git add apps/tiao-web
git commit -m "feat(tiao-web): scaffold app and add SQL guard"
```

---

### Task 2: The view spec model

**Files:**
- Create: `apps/tiao-web/src/tiao_web/spec.py`
- Test: `apps/tiao-web/tests/test_spec.py`

**Interfaces:**
- Consumes: `sql_guard.check_sql`, `sql_guard.SqlNaoPermitido`.
- Produces:
  - `spec.Coluna(campo: str, rotulo: str, formato: str = "texto")`
  - `spec.Grafico(tipo: str, x: str, y: str)`
  - `spec.ViewSpec(titulo: str, sql: str, params: dict, colunas: list[Coluna], ordenar: str | None, grafico: Grafico | None, resumo: list[dict], congelado: bool)`
  - `spec.parse_spec(dados: dict) -> ViewSpec` — raises `spec.SpecInvalido(str)`

- [ ] **Step 1: Write the failing test**

`apps/tiao-web/tests/test_spec.py`:

```python
import pytest

from tiao_web.spec import SpecInvalido, parse_spec

BASE = {
    "titulo": "Pesagem de 21/06/2026",
    "fonte": {
        "sql": "SELECT a.brinco, p.peso_kg FROM pesagens p JOIN animais a ON a.id = p.animal_id WHERE p.data = :data",
        "params": {"data": "2026-06-21"},
    },
    "tabela": {
        "colunas": [
            {"campo": "brinco", "rotulo": "Brinco"},
            {"campo": "peso_kg", "rotulo": "Peso", "formato": "kg"},
        ]
    },
}


def test_spec_minimo_e_aceito():
    s = parse_spec(BASE)
    assert s.titulo == "Pesagem de 21/06/2026"
    assert s.params == {"data": "2026-06-21"}
    assert [c.campo for c in s.colunas] == ["brinco", "peso_kg"]
    assert s.colunas[1].formato == "kg"
    assert s.sql.endswith("LIMIT 500")


def test_param_faltando_e_rejeitado():
    dados = {**BASE, "fonte": {"sql": "SELECT 1 WHERE x = :data", "params": {}}}
    with pytest.raises(SpecInvalido, match="data"):
        parse_spec(dados)


def test_param_sobrando_e_rejeitado():
    dados = {**BASE, "fonte": {"sql": "SELECT 1", "params": {"nao_usado": 1}}}
    with pytest.raises(SpecInvalido, match="nao_usado"):
        parse_spec(dados)


def test_sql_de_escrita_e_rejeitado():
    dados = {**BASE, "fonte": {"sql": "DELETE FROM animais", "params": {}}}
    with pytest.raises(SpecInvalido):
        parse_spec(dados)


def test_titulo_obrigatorio():
    dados = {k: v for k, v in BASE.items() if k != "titulo"}
    with pytest.raises(SpecInvalido, match="titulo"):
        parse_spec(dados)


def test_formato_invalido_e_rejeitado():
    dados = {
        **BASE,
        "tabela": {"colunas": [{"campo": "x", "rotulo": "X", "formato": "foguete"}]},
    }
    with pytest.raises(SpecInvalido, match="foguete"):
        parse_spec(dados)


def test_grafico_precisa_de_colunas_existentes():
    dados = {**BASE, "grafico": {"tipo": "barras", "x": "brinco", "y": "inexistente"}}
    with pytest.raises(SpecInvalido, match="inexistente"):
        parse_spec(dados)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd apps/tiao-web && python -m pytest tests/test_spec.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tiao_web.spec'`

- [ ] **Step 3: Write the implementation**

`apps/tiao-web/src/tiao_web/spec.py`:

```python
"""The contract between the bot and the renderer.

The bot emits one of these; the renderer turns any of them into the same-looking
page. Keeping the shape small is what makes the output consistent.
"""

import re
from dataclasses import dataclass, field

from .sql_guard import SqlNaoPermitido, check_sql

FORMATOS = {"texto", "kg", "reais", "data", "numero"}
TIPOS_GRAFICO = {"barras", "linha"}

# ":nome" not preceded by another colon (so ::cast is not a parameter)
_PARAM = re.compile(r"(?<!:):([a-zA-Z_][a-zA-Z0-9_]*)")


class SpecInvalido(Exception):
    """The spec is malformed."""


@dataclass(frozen=True)
class Coluna:
    campo: str
    rotulo: str
    formato: str = "texto"


@dataclass(frozen=True)
class Grafico:
    tipo: str
    x: str
    y: str


@dataclass(frozen=True)
class ViewSpec:
    titulo: str
    sql: str
    params: dict
    colunas: list
    ordenar: str | None = None
    grafico: Grafico | None = None
    resumo: list = field(default_factory=list)
    congelado: bool = False


def parse_spec(dados: dict) -> ViewSpec:
    if not isinstance(dados, dict):
        raise SpecInvalido("spec precisa ser um objeto")

    titulo = (dados.get("titulo") or "").strip()
    if not titulo:
        raise SpecInvalido("titulo é obrigatório")

    fonte = dados.get("fonte") or {}
    params = fonte.get("params") or {}
    if not isinstance(params, dict):
        raise SpecInvalido("params precisa ser um objeto")

    try:
        sql = check_sql(fonte.get("sql") or "")
    except SqlNaoPermitido as exc:
        raise SpecInvalido(str(exc)) from exc

    usados = set(_PARAM.findall(sql))
    fornecidos = set(params)
    if faltando := usados - fornecidos:
        raise SpecInvalido(f"faltam parâmetros: {', '.join(sorted(faltando))}")
    if sobrando := fornecidos - usados:
        raise SpecInvalido(f"parâmetros não usados: {', '.join(sorted(sobrando))}")

    tabela = dados.get("tabela") or {}
    colunas = []
    for c in tabela.get("colunas") or []:
        formato = c.get("formato", "texto")
        if formato not in FORMATOS:
            raise SpecInvalido(f"formato desconhecido: {formato}")
        colunas.append(Coluna(campo=c["campo"], rotulo=c["rotulo"], formato=formato))
    if not colunas:
        raise SpecInvalido("a tabela precisa de ao menos uma coluna")

    grafico = None
    if g := dados.get("grafico"):
        if g.get("tipo") not in TIPOS_GRAFICO:
            raise SpecInvalido(f"tipo de gráfico desconhecido: {g.get('tipo')}")
        campos = {c.campo for c in colunas}
        for eixo in ("x", "y"):
            if g.get(eixo) not in campos:
                raise SpecInvalido(f"gráfico usa coluna inexistente: {g.get(eixo)}")
        grafico = Grafico(tipo=g["tipo"], x=g["x"], y=g["y"])

    return ViewSpec(
        titulo=titulo,
        sql=sql,
        params=params,
        colunas=colunas,
        ordenar=(tabela.get("ordenar") or None),
        grafico=grafico,
        resumo=list(dados.get("resumo") or []),
        congelado=bool(dados.get("congelado", False)),
    )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd apps/tiao-web && python -m pytest tests/test_spec.py -v`
Expected: PASS — 7 passed

- [ ] **Step 5: Commit**

```bash
git add apps/tiao-web/src/tiao_web/spec.py apps/tiao-web/tests/test_spec.py
git commit -m "feat(tiao-web): add view spec model and validation"
```

---

### Task 3: Bar chart as inline SVG

Server-generated so the page needs no JavaScript and no CDN.

**Files:**
- Create: `apps/tiao-web/src/tiao_web/chart.py`
- Test: `apps/tiao-web/tests/test_chart.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `chart.barras(rotulos: list[str], valores: list[float], *, largura: int = 320, altura: int = 180) -> str` — returns an SVG fragment string; returns `""` when there is nothing to plot.

- [ ] **Step 1: Write the failing test**

`apps/tiao-web/tests/test_chart.py`:

```python
from tiao_web.chart import barras


def test_svg_tem_uma_barra_por_valor():
    svg = barras(["45", "120", "78"], [320, 447, 330])
    assert svg.count("<rect") == 3
    assert svg.startswith("<svg")
    assert "</svg>" in svg


def test_rotulos_aparecem():
    svg = barras(["45", "120"], [320, 447])
    assert ">45<" in svg
    assert ">120<" in svg


def test_lista_vazia_nao_gera_svg():
    assert barras([], []) == ""


def test_valores_iguais_nao_dividem_por_zero():
    svg = barras(["a", "b"], [10, 10])
    assert svg.count("<rect") == 2


def test_rotulo_com_caractere_especial_e_escapado():
    svg = barras(["<b>"], [1])
    assert "<b>" not in svg.split("<svg")[1].replace("<rect", "").replace("<text", "")
    assert "&lt;b&gt;" in svg


def test_saida_e_deterministica():
    assert barras(["a"], [1]) == barras(["a"], [1])
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd apps/tiao-web && python -m pytest tests/test_chart.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tiao_web.chart'`

- [ ] **Step 3: Write the implementation**

`apps/tiao-web/src/tiao_web/chart.py`:

```python
"""Inline SVG charts, generated on the server.

No chart library and no CDN: the page has to render over a weak connection at
the ranch, where a blocked or slow CDN would simply leave a blank space.
"""

from html import escape

MARGEM_BASE = 22


def barras(rotulos, valores, *, largura: int = 320, altura: int = 180) -> str:
    pares = [(r, float(v)) for r, v in zip(rotulos, valores) if v is not None]
    if not pares:
        return ""

    maximo = max(v for _, v in pares) or 1.0
    area = altura - MARGEM_BASE
    passo = largura / len(pares)
    corpo = max(passo * 0.6, 1.0)

    partes = [
        f'<svg viewBox="0 0 {largura} {altura}" width="100%" height="{altura}" '
        f'role="img" class="grafico">'
    ]
    for i, (rotulo, valor) in enumerate(pares):
        h = (valor / maximo) * area
        x = i * passo + (passo - corpo) / 2
        y = area - h
        partes.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{corpo:.1f}" height="{h:.1f}" rx="2"/>'
        )
        partes.append(
            f'<text x="{i * passo + passo / 2:.1f}" y="{altura - 6}" '
            f'text-anchor="middle" class="rotulo">{escape(str(rotulo))}</text>'
        )
    partes.append("</svg>")
    return "".join(partes)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd apps/tiao-web && python -m pytest tests/test_chart.py -v`
Expected: PASS — 6 passed

- [ ] **Step 5: Commit**

```bash
git add apps/tiao-web/src/tiao_web/chart.py apps/tiao-web/tests/test_chart.py
git commit -m "feat(tiao-web): render bar charts as inline SVG"
```

---

### Task 4: The renderer

The single place that decides what a page looks like. Every screen goes through it.

**Files:**
- Create: `apps/tiao-web/src/tiao_web/render.py`
- Create: `apps/tiao-web/src/tiao_web/templates/pagina.html.j2`
- Create: `apps/tiao-web/src/tiao_web/templates/estilo.css`
- Test: `apps/tiao-web/tests/test_render.py`

**Interfaces:**
- Consumes: `spec.ViewSpec`, `spec.Coluna`, `chart.barras`.
- Produces:
  - `render.formatar(valor, formato: str) -> str`
  - `render.render_pagina(s: ViewSpec, linhas: list[dict]) -> str` — full HTML document.

- [ ] **Step 1: Write the failing test**

`apps/tiao-web/tests/test_render.py`:

```python
from tiao_web.render import formatar, render_pagina
from tiao_web.spec import parse_spec

SPEC = parse_spec(
    {
        "titulo": "Pesagem de 21/06/2026",
        "resumo": [{"rotulo": "Cabeças", "valor": "2"}],
        "fonte": {"sql": "SELECT brinco, peso_kg FROM pesagens", "params": {}},
        "tabela": {
            "colunas": [
                {"campo": "brinco", "rotulo": "Brinco"},
                {"campo": "peso_kg", "rotulo": "Peso", "formato": "kg"},
            ]
        },
        "grafico": {"tipo": "barras", "x": "brinco", "y": "peso_kg"},
    }
)
LINHAS = [{"brinco": "367", "peso_kg": 282}, {"brinco": "453", "peso_kg": 284}]


def test_formatar_kg():
    assert formatar(282, "kg") == "282 kg"


def test_formatar_reais():
    assert formatar(2900, "reais") == "R$ 2.900,00"


def test_formatar_data():
    import datetime

    assert formatar(datetime.date(2026, 6, 21), "data") == "21/06/2026"


def test_formatar_vazio_nao_mostra_none():
    assert formatar(None, "kg") == "—"


def test_pagina_tem_titulo_e_linhas():
    html = render_pagina(SPEC, LINHAS)
    assert "Pesagem de 21/06/2026" in html
    assert "367" in html and "282 kg" in html
    assert html.count("<tr") == 3  # header + 2 rows


def test_pagina_tem_resumo_e_grafico():
    html = render_pagina(SPEC, LINHAS)
    assert "Cabeças" in html
    assert "<svg" in html


def test_estilo_vai_embutido_sem_cdn():
    html = render_pagina(SPEC, LINHAS)
    assert "<style>" in html
    assert "http://" not in html and "https://" not in html


def test_sem_linhas_mostra_recado_em_portugues():
    html = render_pagina(SPEC, [])
    assert "Nada anotado" in html
    assert "<svg" not in html


def test_valor_da_linha_e_escapado():
    html = render_pagina(SPEC, [{"brinco": "<script>", "peso_kg": 1}])
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd apps/tiao-web && python -m pytest tests/test_render.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tiao_web.render'`

- [ ] **Step 3: Write the stylesheet**

`apps/tiao-web/src/tiao_web/templates/estilo.css`:

```css
:root { --tinta:#1b1b1b; --papel:#fbf9f4; --linha:#e0dbcf; --destaque:#5a7a3a; }
* { box-sizing:border-box; }
body { margin:0; padding:16px; background:var(--papel); color:var(--tinta);
       font:18px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif; }
h1 { font-size:22px; margin:0 0 4px; }
.resumo { display:flex; flex-wrap:wrap; gap:12px; margin:12px 0 18px; }
.resumo div { background:#fff; border:1px solid var(--linha); border-radius:8px;
              padding:8px 14px; min-width:96px; }
.resumo .rotulo { display:block; font-size:13px; color:#6b6b6b; }
.resumo .valor { font-size:20px; font-weight:600; }
table { width:100%; border-collapse:collapse; background:#fff; }
th,td { padding:12px 10px; text-align:left; border-bottom:1px solid var(--linha); }
th { font-size:14px; text-transform:uppercase; letter-spacing:.03em; color:#6b6b6b; }
td { font-size:19px; }
.grafico { margin:18px 0; }
.grafico rect { fill:var(--destaque); }
.grafico .rotulo { font-size:11px; fill:#6b6b6b; }
.vazio { padding:28px 0; color:#6b6b6b; }
@media (prefers-color-scheme: dark) {
  :root { --tinta:#f2efe8; --papel:#14150f; --linha:#33352b; }
  table,.resumo div { background:#1d1f18; }
}
```

- [ ] **Step 4: Write the template**

`apps/tiao-web/src/tiao_web/templates/pagina.html.j2`:

```jinja
<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ s.titulo }}</title>
<style>{{ estilo }}</style>
</head>
<body>
<h1>{{ s.titulo }}</h1>

{% if s.resumo %}
<div class="resumo">
  {% for item in s.resumo %}
  <div><span class="rotulo">{{ item.rotulo }}</span><span class="valor">{{ item.valor }}</span></div>
  {% endfor %}
</div>
{% endif %}

{% if linhas %}
  {% if grafico %}{{ grafico | safe }}{% endif %}
  <table>
    <tr>{% for c in s.colunas %}<th>{{ c.rotulo }}</th>{% endfor %}</tr>
    {% for linha in linhas %}{% set i = loop.index0 %}
    <tr>{% for c in s.colunas %}<td>{{ celulas[i][loop.index0] }}</td>{% endfor %}</tr>
    {% endfor %}
  </table>
{% else %}
  <p class="vazio">Nada anotado por aqui ainda, patrão.</p>
{% endif %}
</body>
</html>
```

> The row index is captured with `{% set i = loop.index0 %}` because the inner column loop
> shadows `loop`, and `celulas` is indexed by row then column.

- [ ] **Step 5: Write the renderer**

`apps/tiao-web/src/tiao_web/render.py`:

```python
"""Spec + rows -> HTML. The only place that decides how a page looks.

Formatting lives here rather than in the SQL so that a weight renders identically
on every screen, whatever query produced it.
"""

import datetime
from decimal import Decimal
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .chart import barras

TEMPLATES = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(TEMPLATES),
    autoescape=select_autoescape(["html", "j2"]),
)
_estilo = (TEMPLATES / "estilo.css").read_text(encoding="utf-8")


def formatar(valor, formato: str) -> str:
    if valor is None or valor == "":
        return "—"
    if formato == "kg":
        return f"{_num(valor):g} kg"
    if formato == "reais":
        inteiro = f"{_num(valor):,.2f}"
        return "R$ " + inteiro.replace(",", "@").replace(".", ",").replace("@", ".")
    if formato == "data":
        if isinstance(valor, (datetime.date, datetime.datetime)):
            return valor.strftime("%d/%m/%Y")
        return str(valor)
    if formato == "numero":
        return f"{_num(valor):g}"
    return str(valor)


def _num(valor):
    if isinstance(valor, Decimal):
        return float(valor)
    return float(valor) if isinstance(valor, (int, float)) else float(str(valor))


def render_pagina(s, linhas) -> str:
    celulas = [[formatar(linha.get(c.campo), c.formato) for c in s.colunas] for linha in linhas]

    grafico = ""
    if s.grafico and linhas:
        grafico = barras(
            [str(linha.get(s.grafico.x)) for linha in linhas],
            [linha.get(s.grafico.y) for linha in linhas],
        )

    return _env.get_template("pagina.html.j2").render(
        s=s, linhas=linhas, celulas=celulas, grafico=grafico, estilo=_estilo
    )
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `cd apps/tiao-web && python -m pytest tests/test_render.py -v`
Expected: PASS — 9 passed

- [ ] **Step 7: Commit**

```bash
git add apps/tiao-web/src/tiao_web/render.py apps/tiao-web/src/tiao_web/templates apps/tiao-web/tests/test_render.py
git commit -m "feat(tiao-web): add the fixed page renderer"
```

---

### Task 5: Postgres roles under Ansible

Creates the read-only role the app uses, and brings the hand-created `tiao_user` / `tiao_database` under Ansible in the same change.

**Files:**
- Modify: `ansible/inventories/local/host_vars/database/postgresql_databases.yml`
- Modify: `ansible/inventories/local/group_vars/all/vault.yml` (ansible-vault edit)
- Create: `ansible/playbooks/vms/database-tiao-grants.yml`

**Interfaces:**
- Consumes: nothing.
- Produces: role `tiao_web_user` on `tiao_database` at 192.168.1.103, `SELECT`-only, `statement_timeout=5s`, `default_transaction_read_only=on`. Password in `vault.database.tiao_web_user_pw`.

- [ ] **Step 1: Read the live password so the vault records the current value**

```bash
ssh root@hermes-vm.local.batistela.tech \
  'grep -E "^\s*PGPASSWORD=" /root/.hermes/profiles/tiao/.env | cut -d= -f2-'
```

> This value goes into the vault **as-is**. Writing a different one rewrites the live password
> on the next `make play-database`, and the bot loses the ledger — surfacing only as Tião
> saying "deu ruim, patrão".

- [ ] **Step 2: Add both secrets to the vault**

```bash
cd ansible && ../.venv/bin/ansible-vault edit inventories/local/group_vars/all/vault.yml
```

Under `database:` add:

```yaml
    tiao_user_pw: "<the value printed in Step 1>"
    tiao_web_user_pw: "<a new strong password you generate>"
```

- [ ] **Step 3: Declare the users and database**

In `ansible/inventories/local/host_vars/database/postgresql_databases.yml`, append to
`postgresql_users`:

```yaml
  - name: tiao_user
    password: "{{ vault.database.tiao_user_pw }}"
  - name: tiao_web_user
    password: "{{ vault.database.tiao_web_user_pw }}"
```

and to `postgresql_databases`:

```yaml
  - name: tiao_database
    owner: tiao_user
```

- [ ] **Step 4: Write the grants playbook**

`ansible/playbooks/vms/database-tiao-grants.yml`:

```yaml
---
- name: "Grant read-only access on tiao_database to tiao_web_user"
  hosts: database
  gather_facts: false
  become: true
  become_user: postgres
  tasks:
    - name: Allow connecting to the database
      community.postgresql.postgresql_privs:
        db: tiao_database
        type: database
        objs: tiao_database
        privs: CONNECT
        roles: tiao_web_user

    - name: Allow using the public schema
      community.postgresql.postgresql_privs:
        db: tiao_database
        type: schema
        objs: public
        privs: USAGE
        roles: tiao_web_user

    - name: Grant SELECT on existing tables
      community.postgresql.postgresql_privs:
        db: tiao_database
        type: table
        schema: public
        objs: ALL_IN_SCHEMA
        privs: SELECT
        roles: tiao_web_user

    # Without this, any table created later is invisible to the web layer and the
    # symptom surfaces weeks on as "a screen disappeared".
    - name: Grant SELECT on tables created later by tiao_user
      community.postgresql.postgresql_privs:
        db: tiao_database
        type: default_privs
        schema: public
        objs: TABLES
        privs: SELECT
        roles: tiao_web_user
        target_roles: tiao_user

    # Role-scoped, so every session this user opens is read-only and time-limited
    # regardless of what the app sends.
    - name: Force read-only, time-limited sessions for the role
      community.postgresql.postgresql_query:
        db: tiao_database
        query: "{{ item }}"
      loop:
        - "ALTER ROLE tiao_web_user SET statement_timeout = '5s'"
        - "ALTER ROLE tiao_web_user SET default_transaction_read_only = on"
```

- [ ] **Step 5: Run it**

```bash
cd ansible && ../.venv/bin/ansible-playbook -i inventories/local playbooks/vms/database-tiao-grants.yml
```

- [ ] **Step 6: Verify the role is genuinely read-only**

```bash
ssh root@hermes-vm.local.batistela.tech \
  'PGHOST=192.168.1.103 PGDATABASE=tiao_database PGUSER=tiao_web_user PGPASSWORD=<new> \
   psql -X -tAc "SELECT count(*) FROM animais;" && \
   PGHOST=192.168.1.103 PGDATABASE=tiao_database PGUSER=tiao_web_user PGPASSWORD=<new> \
   psql -X -tAc "INSERT INTO animais (brinco) VALUES (:.q);" ; echo "exit=$?"'
```

Expected: the `SELECT` returns a count; the `INSERT` fails with a permission or read-only
transaction error, and the exit code is non-zero.

- [ ] **Step 7: Confirm the role contains the function-call bypasses**

The SQL guard cannot catch a write reached through a function call — `SELECT setval(...)` carries
no DML keyword. The design answer is that the database role refuses them; this step proves it
rather than assuming it. Run each as `tiao_web_user`:

```bash
ssh root@hermes-vm.local.batistela.tech 'bash -s' <<'EOF'
export PGHOST=192.168.1.103 PGDATABASE=tiao_database PGUSER=tiao_web_user PGPASSWORD='<new>'
for q in "SELECT setval('animais_id_seq', 100)" \
         "SELECT lo_import('/etc/passwd')" \
         "SELECT pg_terminate_backend(1)"; do
  printf '%-46s -> ' "$q"
  psql -X -tAc "$q" 2>&1 | head -1
done
EOF
```

Expected: `setval` and `lo_import` fail with a read-only-transaction or permission error;
`pg_terminate_backend` either fails on privilege or affects nothing outside this role's own
backends. **If any of the three succeeds, stop** — the guard would then be the only layer
standing, and that is not the design.

- [ ] **Step 8: Confirm the bot still has its database**

```bash
ssh root@hermes-vm.local.batistela.tech \
  'set -a; . /root/.hermes/profiles/tiao/.env; set +a; psql -X -tAc "SELECT current_user;"'
```

Expected: `tiao_user`. If this fails, the vault password did not match the live one — fix the
vault value and re-run, before going further.

- [ ] **Step 9: Commit**

```bash
git add ansible/inventories/local/host_vars/database/postgresql_databases.yml \
        ansible/inventories/local/group_vars/all/vault.yml \
        ansible/playbooks/vms/database-tiao-grants.yml
git commit -m "feat(database): manage tiao roles and add read-only tiao_web_user"
```

---

### Task 6: Database access and the `pesagens` view

**Files:**
- Create: `apps/tiao-web/src/tiao_web/db.py`
- Create: `apps/tiao-web/src/tiao_web/views.py`
- Test: `apps/tiao-web/tests/test_views.py`

**Interfaces:**
- Consumes: `spec.ViewSpec`, `spec.parse_spec`.
- Produces:
  - `db.executar(s: ViewSpec) -> list[dict]`
  - `views.pesagens(data: str | None) -> ViewSpec`
  - `views.NOMEADAS: dict[str, callable]`

- [ ] **Step 1: Write the failing test**

`apps/tiao-web/tests/test_views.py`:

```python
import datetime

from tiao_web.views import pesagens


def test_pesagens_monta_spec_valido_com_data():
    s = pesagens("2026-06-21")
    assert s.params == {"data": "2026-06-21"}
    assert "pesagens" in s.sql
    assert [c.campo for c in s.colunas] == ["brinco", "peso_kg", "categoria"]
    assert s.grafico is not None


def test_pesagens_sem_data_usa_hoje():
    s = pesagens(None)
    assert s.params["data"] == datetime.date.today().isoformat()


def test_titulo_e_em_portugues_com_data_legivel():
    s = pesagens("2026-06-21")
    assert s.titulo == "Pesagem de 21/06/2026"


def test_data_invalida_cai_para_hoje():
    s = pesagens("nao-e-data")
    assert s.params["data"] == datetime.date.today().isoformat()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd apps/tiao-web && python -m pytest tests/test_views.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tiao_web.views'`

- [ ] **Step 3: Write the database layer**

`apps/tiao-web/src/tiao_web/db.py`:

```python
"""Read-only database access.

SQLAlchemy's ``text()`` binds ``:name`` parameters through the driver, so the
values Seu Jader picks in a filter can never become part of the statement.
"""

import os

from sqlalchemy import create_engine, text

_engine = None


def engine():
    global _engine
    if _engine is None:
        url = (
            f"postgresql+psycopg://{os.environ['PGUSER']}:{os.environ['PGPASSWORD']}"
            f"@{os.environ['PGHOST']}:{os.environ.get('PGPORT', '5432')}"
            f"/{os.environ['PGDATABASE']}"
        )
        _engine = create_engine(url, pool_pre_ping=True, pool_size=2, max_overflow=2)
    return _engine


def executar(s) -> list[dict]:
    with engine().connect() as conexao:
        resultado = conexao.execute(text(s.sql), s.params)
        return [dict(linha) for linha in resultado.mappings()]
```

- [ ] **Step 4: Write the named view**

`apps/tiao-web/src/tiao_web/views.py`:

```python
"""Named views are stored specs, not separate code paths.

Every screen therefore renders through the same components, which is what keeps
two pages on unrelated subjects looking identical.
"""

import datetime

from .spec import parse_spec

SQL_PESAGENS = """
SELECT a.brinco, p.peso_kg, a.categoria
FROM pesagens p
JOIN animais a ON a.id = p.animal_id
WHERE p.data = :data
ORDER BY a.brinco
"""


def _data_valida(data: str | None) -> datetime.date:
    try:
        return datetime.date.fromisoformat(data) if data else datetime.date.today()
    except (TypeError, ValueError):
        return datetime.date.today()


def pesagens(data: str | None):
    dia = _data_valida(data)
    return parse_spec(
        {
            "titulo": f"Pesagem de {dia.strftime('%d/%m/%Y')}",
            "fonte": {"sql": SQL_PESAGENS, "params": {"data": dia.isoformat()}},
            "tabela": {
                "colunas": [
                    {"campo": "brinco", "rotulo": "Brinco"},
                    {"campo": "peso_kg", "rotulo": "Peso", "formato": "kg"},
                    {"campo": "categoria", "rotulo": "Categoria"},
                ]
            },
            "grafico": {"tipo": "barras", "x": "brinco", "y": "peso_kg"},
        }
    )


NOMEADAS = {"pesagens": pesagens}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd apps/tiao-web && python -m pytest tests/test_views.py -v`
Expected: PASS — 4 passed

- [ ] **Step 6: Verify the query against the real database**

```bash
ssh root@hermes-vm.local.batistela.tech \
 'PGHOST=192.168.1.103 PGDATABASE=tiao_database PGUSER=tiao_web_user PGPASSWORD=<new> \
  psql -X -P pager=off -c "SELECT a.brinco, p.peso_kg, a.categoria FROM pesagens p JOIN animais a ON a.id = p.animal_id WHERE p.data = CURRENT_DATE ORDER BY a.brinco;"'
```

Expected: runs without error (0 rows is fine — the ledger is empty until the bot records).

- [ ] **Step 7: Commit**

```bash
git add apps/tiao-web/src/tiao_web/db.py apps/tiao-web/src/tiao_web/views.py apps/tiao-web/tests/test_views.py
git commit -m "feat(tiao-web): add read-only db access and the pesagens view"
```

---

### Task 7: The HTTP application

**Files:**
- Create: `apps/tiao-web/src/tiao_web/app.py`
- Test: `apps/tiao-web/tests/test_app.py`

**Interfaces:**
- Consumes: `views.NOMEADAS`, `db.executar`, `render.render_pagina`.
- Produces: `app.app` — a Starlette ASGI application exposing `GET /saude` and `GET /pesagens`.

- [ ] **Step 1: Write the failing test**

`apps/tiao-web/tests/test_app.py`:

```python
import pytest
from starlette.testclient import TestClient

import tiao_web.app as modulo


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setattr(
        modulo, "executar", lambda s: [{"brinco": "367", "peso_kg": 282, "categoria": "novilha"}]
    )
    return TestClient(modulo.app)


def test_saude_responde_ok(cliente):
    r = cliente.get("/saude")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_pesagens_renderiza_html(cliente):
    r = cliente.get("/pesagens?data=2026-06-21")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Pesagem de 21/06/2026" in r.text
    assert "367" in r.text and "282 kg" in r.text


def test_falha_de_banco_mostra_recado_de_peao(cliente, monkeypatch):
    def explode(_s):
        raise RuntimeError("connection refused to 192.168.1.103")

    monkeypatch.setattr(modulo, "executar", explode)
    r = cliente.get("/pesagens")
    assert r.status_code == 200
    assert "deu uma encrenca" in r.text.lower()
    assert "192.168.1.103" not in r.text
    assert "RuntimeError" not in r.text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd apps/tiao-web && python -m pytest tests/test_app.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tiao_web.app'`

- [ ] **Step 3: Write the implementation**

`apps/tiao-web/src/tiao_web/app.py`:

```python
"""HTTP surface.

Read routes only in phase 1. There is no login here on purpose: Pangolin checks
the PIN at the edge, before a request reaches this VM.
"""

import logging

from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route

from .db import executar
from .render import render_pagina
from .views import NOMEADAS

logger = logging.getLogger("tiao_web")

RECADO_ERRO = (
    "<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>"
    "<meta name='viewport' content='width=device-width, initial-scale=1'>"
    "<title>Caderneta</title></head><body style=\"font:18px system-ui;padding:24px\">"
    "<p>Ih, patrão, deu uma encrenca aqui pra abrir a caderneta. Tenta de novo daqui a pouco.</p>"
    "</body></html>"
)


async def saude(request):
    return JSONResponse({"status": "ok"})


async def pesagens(request):
    s = NOMEADAS["pesagens"](request.query_params.get("data"))
    try:
        linhas = executar(s)
    except Exception:
        # The technical detail goes to the log, never to Seu Jader.
        logger.exception("falha ao consultar a caderneta")
        return HTMLResponse(RECADO_ERRO, status_code=200)
    return HTMLResponse(render_pagina(s, linhas))


app = Starlette(
    routes=[
        Route("/saude", saude),
        Route("/pesagens", pesagens),
    ]
)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd apps/tiao-web && python -m pytest tests/test_app.py -v`
Expected: PASS — 3 passed

- [ ] **Step 5: Run the whole suite**

Run: `cd apps/tiao-web && python -m pytest -v`
Expected: PASS — every test in the suite green

- [ ] **Step 6: Commit**

```bash
git add apps/tiao-web/src/tiao_web/app.py apps/tiao-web/tests/test_app.py
git commit -m "feat(tiao-web): add HTTP routes for pesagens and health"
```

---

### Task 8: Container image and Ansible deployment

**Files:**
- Create: `apps/tiao-web/Dockerfile`
- Create: `ansible/roles/tiao_web/defaults/main.yml`
- Create: `ansible/roles/tiao_web/tasks/main.yml`
- Create: `ansible/roles/tiao_web/templates/docker-compose.yml.j2`
- Create: `ansible/roles/tiao_web/templates/env.j2`
- Modify: `ansible/playbooks/vms/hermes.yml`
- Create: `ansible/inventories/local/host_vars/hermes/deploy_apps.yml`

**Interfaces:**
- Consumes: the app package from Tasks 1–7; `vault.database.tiao_web_user_pw` from Task 5.
- Produces: `tiao-web` container on the `hermes` VM, `192.168.1.111:8790` (read) and `127.0.0.1:8791` (write, unused until phase 3).

- [ ] **Step 1: Write the Dockerfile**

`apps/tiao-web/Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

EXPOSE 8790
CMD ["uvicorn", "tiao_web.app:app", "--host", "0.0.0.0", "--port", "8790"]
```

- [ ] **Step 2: Build it locally to prove it works**

```bash
./scripts/homelab-apps build tiao-web
```

Expected: image builds with no error.

- [ ] **Step 3: Write the role defaults**

`ansible/roles/tiao_web/defaults/main.yml`:

```yaml
---
tiao_web_compose_dir: /opt/tiao-web
tiao_web_state_dir: /var/lib/tiao-web
tiao_web_image: "ghcr.io/mathbatistela/homelab/tiao-web:sha-REPLACE_WITH_BUILT_SHA"
tiao_web_read_port: 8790
tiao_web_write_port: 8791
tiao_web_lan_ip: "{{ ansible_host }}"
tiao_web_db_host: "{{ hostvars['database'].ansible_host }}"
tiao_web_db_name: tiao_database
tiao_web_db_user: tiao_web_user
tiao_web_ghcr_user: mathbatistela
```

- [ ] **Step 4: Write the compose template**

`ansible/roles/tiao_web/templates/docker-compose.yml.j2`:

```yaml
services:
  tiao-web:
    image: {{ tiao_web_image }}
    container_name: tiao-web
    restart: unless-stopped
    env_file: .env
    ports:
      # Read routes: LAN only, reached by Pangolin. Never published on 0.0.0.0.
      - "{{ tiao_web_lan_ip }}:{{ tiao_web_read_port }}:8790"
      # Spec creation: loopback only, reached by the natively-running bot.
      - "127.0.0.1:{{ tiao_web_write_port }}:8791"
    volumes:
      - {{ tiao_web_state_dir }}:/var/lib/tiao-web
```

- [ ] **Step 5: Write the env template**

`ansible/roles/tiao_web/templates/env.j2`:

```jinja
PGHOST={{ tiao_web_db_host }}
PGPORT=5432
PGDATABASE={{ tiao_web_db_name }}
PGUSER={{ tiao_web_db_user }}
PGPASSWORD={{ vault.database.tiao_web_user_pw }}
```

- [ ] **Step 6: Write the tasks, mirroring `hermes_tools`**

`ansible/roles/tiao_web/tasks/main.yml`:

```yaml
---
- name: Ensure tiao-web directories exist
  ansible.builtin.file:
    path: "{{ item }}"
    state: directory
    owner: root
    group: root
    mode: "0755"
  loop:
    - "{{ tiao_web_compose_dir }}"
    - "{{ tiao_web_state_dir }}"

- name: Log in to GHCR to pull the tiao-web image
  community.docker.docker_login:
    registry_url: ghcr.io
    username: "{{ tiao_web_ghcr_user }}"
    password: "{{ deploy_webhook_ghcr_token }}"
  no_log: true

- name: Copy docker-compose file for tiao-web
  ansible.builtin.template:
    src: docker-compose.yml.j2
    dest: "{{ tiao_web_compose_dir }}/docker-compose.yml"
    owner: root
    group: root
    mode: "0644"

- name: Copy .env file for tiao-web
  ansible.builtin.template:
    src: env.j2
    dest: "{{ tiao_web_compose_dir }}/.env"
    owner: root
    group: root
    mode: "0600"

- name: Deploy tiao-web using docker-compose
  community.docker.docker_compose_v2:
    project_src: "{{ tiao_web_compose_dir }}"
    state: present
    pull: policy
```

- [ ] **Step 7: Give the hermes host GHCR pull credentials**

`ansible/inventories/local/host_vars/hermes/deploy_apps.yml`:

```yaml
---
deploy_webhook_ghcr_token: "{{ vault.tools.deploy_webhook_ghcr_token }}"
```

> `hermes_tools` reuses this same vault key on the `tools` host; the `hermes` host simply had
> no app pulling from GHCR until now.

- [ ] **Step 8: Add the role to the hermes playbook**

`ansible/playbooks/vms/hermes.yml`:

```yaml
---
- name: "Configure hermes VM"
  hosts: hermes
  gather_facts: true
  become: true
  roles:
    - hermes
    - dev_dependencies
    - tiao_web
```

- [ ] **Step 9: Push so CI builds the image, then deploy**

The CI workflow only builds on a push to `main`, and a pull_request build sets `push: false`, so
neither publishes an image for this branch. Use `workflow_dispatch`, which the workflow supports
via its `app` input and which does push — it tags `sha-<commit>` (never `latest`, which is gated
on the default branch). This gets a genuine CI-built image without merging to `main`, and pinning
an exact tag is better practice than chasing `latest` anyway.

```bash
git add apps/tiao-web/Dockerfile ansible/roles/tiao_web \
        ansible/playbooks/vms/hermes.yml \
        ansible/inventories/local/host_vars/hermes/deploy_apps.yml
git commit -m "feat(tiao-web): containerise and deploy to the hermes VM"
git push -u origin feat/tiao-web-fase-1

gh workflow run apps.yml --ref feat/tiao-web-fase-1 -f app=tiao-web
gh run watch "$(gh run list --workflow=apps.yml --branch=feat/tiao-web-fase-1 --limit=1 --json databaseId --jq '.[0].databaseId')"
```

Then set `tiao_web_image` in `ansible/roles/tiao_web/defaults/main.yml` to the exact tag the run
published (`ghcr.io/mathbatistela/homelab/tiao-web:sha-<commit>`), commit that, and deploy:

```bash
make play-hermes
```

- [ ] **Step 10: Verify the container serves on the LAN and not on the internet**

```bash
ssh root@hermes-vm.local.batistela.tech 'docker ps --filter name=tiao-web --format "{{.Status}}"'
curl -s -o /dev/null -w "LAN read  -> HTTP %{http_code}\n" http://192.168.1.111:8790/saude
ssh root@hermes-vm.local.batistela.tech \
  'ss -tlnp | grep -E "8790|8791"'
```

Expected: container `Up`; the health check returns 200 from the LAN; `ss` shows 8790 bound to
`192.168.1.111` and 8791 bound to `127.0.0.1` — **not** `0.0.0.0`.

---

### Task 9: Public exposure through Pangolin

**Files:**
- Create: `config/fragments/pangolin/tiao.yml`

**Interfaces:**
- Consumes: the running container from Task 8.
- Produces: `https://tiao.batistela.tech`, PIN-gated.

- [ ] **Step 1: Write the fragment**

`config/fragments/pangolin/tiao.yml`:

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

> No Terraform change: `terraform/cloud/dns.tf` already publishes a `*` A record for the zone
> pointing at the Pangolin host, so `tiao.batistela.tech` resolves today. The fragment is picked
> up automatically by the `fileglob` in `ansible/playbooks/vms/pangolin.yml`.

- [ ] **Step 2: Validate and deploy**

```bash
make validate
make play-pangolin
```

Expected: `validate` passes; the play converges.

- [ ] **Step 3: Verify the PIN actually gates the page**

```bash
curl -s -o /dev/null -w "sem PIN -> HTTP %{http_code}\n" https://tiao.batistela.tech/pesagens
```

Expected: a redirect or 401 — **not** 200. A 200 here means the page is open to the internet;
stop and fix before going further.

- [ ] **Step 4: Verify the real path end to end**

Open `https://tiao.batistela.tech/pesagens` in a browser, enter `240810`, and confirm the page
renders with the Portuguese empty-state message ("Nada anotado por aqui ainda, patrão.") while
the ledger is still empty.

- [ ] **Step 5: Seed one weighing and confirm live data**

```bash
ssh root@hermes-vm.local.batistela.tech 'bash -s' <<'EOF'
set -a; . /root/.hermes/profiles/tiao/.env; set +a
psql -X -v ON_ERROR_STOP=1 <<'SQL'
INSERT INTO animais (brinco, categoria) VALUES ('367','novilha') ON CONFLICT (brinco) DO NOTHING;
INSERT INTO pesagens (animal_id, data, peso_kg)
SELECT id, CURRENT_DATE, 282 FROM animais WHERE brinco='367'
ON CONFLICT (animal_id, data) DO UPDATE SET peso_kg = EXCLUDED.peso_kg;
SQL
EOF
```

Reload the page: the row and the bar chart must appear. Then remove the seed:

```bash
ssh root@hermes-vm.local.batistela.tech 'bash -s' <<'EOF'
set -a; . /root/.hermes/profiles/tiao/.env; set +a
psql -X -tAc "DELETE FROM pesagens; DELETE FROM animais WHERE brinco='367';"
EOF
```

- [ ] **Step 6: Open it on a phone**

The only test that says whether it works *for Seu Jader*: text large enough to read in the sun,
no horizontal scrolling, no technical words anywhere on screen.

- [ ] **Step 7: Commit**

```bash
git add config/fragments/pangolin/tiao.yml
git commit -m "feat(pangolin): expose tiao.batistela.tech with PIN"
```

---

## Done when

- `https://tiao.batistela.tech/pesagens` asks for the PIN, then renders the day's weighing live.
- `apps/tiao-web` tests pass; `./scripts/homelab-apps validate` and `make validate` pass.
- `tiao_web_user` can read and provably cannot write.
- The bot still owns its database (`SELECT current_user` returns `tiao_user`).
- Ports 8790/8791 are bound to the LAN IP and loopback respectively, never `0.0.0.0`.

Phases 2 (remaining named views) and 3 (`POST /specs`, `/v/<token>`, bot link skill) are separate
plans built on this renderer.

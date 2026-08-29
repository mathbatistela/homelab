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

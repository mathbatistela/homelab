"""The contract between the bot and the renderer.

The bot emits one of these; the renderer turns any of them into the same-looking
page. Keeping the shape small is what makes the output consistent.
"""

from dataclasses import dataclass, field

from sqlalchemy import text

from .sql_guard import SqlNaoPermitido, check_sql

FORMATOS = {"texto", "kg", "reais", "data", "numero"}
TIPOS_GRAFICO = {"barras", "linha"}


class SpecInvalido(Exception):
    """The spec is malformed."""


def _params_da_sql(sql: str) -> set:
    """The placeholders SQLAlchemy will actually bind when this statement runs.

    Read off ``text()`` — the very object db.executar hands to the driver —
    rather than scanned out of the SQL a second way here. Ingest validation and
    execution then cannot disagree about what counts as a placeholder, because
    only one of them is reading.

    They used to. A regex here read ``:data::date`` as ``data`` while ``text()``
    reads it as ``dat``, so that spec passed parse_spec and raised at executar:
    Seu Jader gets "deu uma encrenca" on a link the bot had just sent him.
    Phase-1 SQL is fixed, so it could not happen yet — but ``:data::date`` is
    the natural Postgres form for a model to emit, and phase 3 lets the model
    write the SQL.

    The consequence to know: a cast on a bound value must be written
    ``CAST(:data AS date)``. ``:data::date`` is refused at ingest, where the bot
    can still fix it, instead of on the reader's screen.

    ``_bindparams`` is private, but it is the exact answer, and reimplementing
    it is precisely what caused the bug.
    """
    return set(text(sql)._bindparams)


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
    # This is the trust boundary for model-authored JSON: any field of the
    # wrong shape must end as SpecInvalido, never a raw AttributeError,
    # KeyError or TypeError leaking past this function.
    if not isinstance(dados, dict):
        raise SpecInvalido("spec precisa ser um objeto")

    titulo = dados.get("titulo")
    if not isinstance(titulo, str) or not titulo.strip():
        raise SpecInvalido("titulo é obrigatório")
    titulo = titulo.strip()

    fonte = dados.get("fonte")
    if fonte is None:
        fonte = {}
    if not isinstance(fonte, dict):
        raise SpecInvalido("fonte precisa ser um objeto")

    params = fonte.get("params")
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise SpecInvalido("params precisa ser um objeto")

    try:
        sql = check_sql(fonte.get("sql") or "")
    except SqlNaoPermitido as exc:
        raise SpecInvalido(str(exc)) from exc

    usados = _params_da_sql(sql)
    fornecidos = set(params)
    if faltando := usados - fornecidos:
        raise SpecInvalido(f"faltam parâmetros: {', '.join(sorted(faltando))}")
    if sobrando := fornecidos - usados:
        raise SpecInvalido(f"parâmetros não usados: {', '.join(sorted(sobrando))}")

    tabela = dados.get("tabela")
    if tabela is None:
        tabela = {}
    if not isinstance(tabela, dict):
        raise SpecInvalido("tabela precisa ser um objeto")

    colunas_brutas = tabela.get("colunas")
    if colunas_brutas is None:
        colunas_brutas = []
    if not isinstance(colunas_brutas, list):
        raise SpecInvalido("colunas precisa ser uma lista")

    colunas = []
    for c in colunas_brutas:
        if not isinstance(c, dict):
            raise SpecInvalido("cada coluna precisa ser um objeto")
        campo = c.get("campo")
        if not isinstance(campo, str) or not campo:
            raise SpecInvalido("coluna sem campo")
        rotulo = c.get("rotulo")
        if not isinstance(rotulo, str) or not rotulo:
            raise SpecInvalido("coluna sem rotulo")
        formato = c.get("formato", "texto")
        if formato not in FORMATOS:
            raise SpecInvalido(f"formato desconhecido: {formato}")
        colunas.append(Coluna(campo=campo, rotulo=rotulo, formato=formato))
    if not colunas:
        raise SpecInvalido("a tabela precisa de ao menos uma coluna")

    grafico = None
    g = dados.get("grafico")
    if g:
        if not isinstance(g, dict):
            raise SpecInvalido("grafico precisa ser um objeto")
        if g.get("tipo") not in TIPOS_GRAFICO:
            raise SpecInvalido(f"tipo de gráfico desconhecido: {g.get('tipo')}")
        campos = {c.campo for c in colunas}
        for eixo in ("x", "y"):
            if g.get(eixo) not in campos:
                raise SpecInvalido(f"gráfico usa coluna inexistente: {g.get(eixo)}")
        grafico = Grafico(tipo=g["tipo"], x=g["x"], y=g["y"])

    resumo_bruto = dados.get("resumo")
    if resumo_bruto is None:
        resumo_bruto = []
    if not isinstance(resumo_bruto, list):
        raise SpecInvalido("resumo precisa ser uma lista")
    resumo = []
    for item in resumo_bruto:
        if not isinstance(item, dict) or "rotulo" not in item or "valor" not in item:
            raise SpecInvalido("cada item do resumo precisa de rotulo e valor")
        resumo.append(item)

    return ViewSpec(
        titulo=titulo,
        sql=sql,
        params=params,
        colunas=colunas,
        ordenar=(tabela.get("ordenar") or None),
        grafico=grafico,
        resumo=resumo,
        congelado=bool(dados.get("congelado", False)),
    )

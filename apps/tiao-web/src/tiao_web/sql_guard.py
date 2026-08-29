"""Guard for model-authored SQL.

The bot writes the SELECT in a view spec, so this is the boundary that keeps a
generated statement from doing anything but reading. It is one of three
independent layers: the database role is SELECT-only and read-only, and every
value the user picks is bound rather than interpolated.
"""

import sqlparse


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

    # Defence in depth: get_type() only inspects the leading command, so a
    # CTE whose inner statement writes still reports SELECT at the top
    # level. Scan every token for a nested DML keyword instead of matching
    # on text: TRUNCATE, COPY and VACUUM are non-reserved words in
    # PostgreSQL and are legal column names or aliases (e.g.
    # "SELECT total AS truncate FROM animais"), so a text/keyword-class
    # match on those would reject a legitimate read. SELECT, INSERT,
    # UPDATE and DELETE are reserved words that sqlparse only ever tags as
    # Keyword.DML, so this check has no such false positive.
    for token in analisada.flatten():
        if token.ttype is sqlparse.tokens.Keyword.DML and token.normalized.upper() != "SELECT":
            raise SqlNaoPermitido(f"comando nao permitido: {token.normalized}")

    # The cap is a ceiling, not a default. Nothing behind this layer bounds the
    # result size: statement_timeout is set on the role and the role can unset
    # it, and the pool is two connections deep — a single unbounded read is
    # enough to hold one of them and hand the phone a page it cannot render.
    tem_limit, alvo = _limit_do_topo(analisada)
    if not tem_limit:
        return f"{texto} LIMIT {limite}"
    if alvo is None:
        raise SqlNaoPermitido("LIMIT sem valor")
    if _acima_do_teto(alvo, limite):
        alvo.ttype = sqlparse.tokens.Number.Integer
        alvo.value = alvo.normalized = str(limite)
        texto = str(analisada)
    return texto


def _limit_do_topo(analisada):
    """Whether the statement declares a LIMIT of its own, and its value token.

    Only the top level counts. The old check matched the keyword anywhere in
    the flattened stream, so ``SELECT * FROM (SELECT ... LIMIT 10) t`` read as
    "already limited" and got no outer cap at all — a subquery's limit says
    nothing about how many rows come back.
    """
    tokens = [t for t in analisada.tokens if not t.is_whitespace]
    for i, token in enumerate(tokens):
        if token.ttype in sqlparse.tokens.Keyword and token.normalized.upper() == "LIMIT":
            return True, (tokens[i + 1] if i + 1 < len(tokens) else None)
    return False, None


def _acima_do_teto(alvo, limite: int) -> bool:
    """True unless the declared limit is an integer literal within the cap.

    One rule and no exceptions: anything that cannot be read as a small enough
    integer — ``LIMIT ALL``, a bind parameter, an expression — counts as
    unbounded and is replaced by the cap.
    """
    if alvo.ttype not in sqlparse.tokens.Number:
        return True
    try:
        return int(alvo.value) > limite
    except ValueError:
        return True

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

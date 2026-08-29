"""Named views are stored specs, not separate code paths.

Every screen therefore renders through the same components, which is what keeps
two pages on unrelated subjects looking identical.
"""

import datetime
from dataclasses import replace

from .render import formatar
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


def resumir_pesagens(s, linhas: list[dict]):
    """Cabeças and Média — the line a rancher glances at first.

    Computed after the query rather than written into the spec, because the
    values come from the rows. Formatting goes through render.formatar so an
    average weight reads exactly like a weight in the table below it.
    """
    if not linhas:
        # The page already says "Nada anotado por aqui ainda, patrão."
        return replace(s, resumo=[])

    resumo = [{"rotulo": "Cabeças", "valor": formatar(len(linhas), "numero")}]
    if (media := _media_kg(linhas)) is not None:
        resumo.append({"rotulo": "Média", "valor": formatar(round(media), "kg")})
    return replace(s, resumo=resumo)


def _media_kg(linhas: list[dict]) -> float | None:
    """Mean weight over the rows that carry one.

    Every row is a head, but a weighing can be missing or arrive as something
    that is not a number, and one bad row must not cost the whole summary.
    """
    pesos = []
    for linha in linhas:
        try:
            pesos.append(float(linha.get("peso_kg")))
        except (TypeError, ValueError):
            continue
    return sum(pesos) / len(pesos) if pesos else None


NOMEADAS = {"pesagens": pesagens}

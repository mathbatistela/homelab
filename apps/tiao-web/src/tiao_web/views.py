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

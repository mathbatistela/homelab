"""Inline SVG charts, generated on the server.

No chart library and no CDN: the page has to render over a weak connection at
the ranch, where a blocked or slow CDN would simply leave a blank space.
"""

import math
from html import escape

MARGEM_BASE = 22


def _numero(valor):
    """The value as a plottable float, or None to leave it out of the chart.

    parse_spec checks that grafico.y names a column that exists, not that the
    column holds numbers, so a perfectly valid spec can aim the chart at a text
    column. A value that is not a finite number is dropped exactly like a
    missing one — nan and inf serialise into the geometry attributes as "nan"
    and "inf", which browsers refuse to paint. Losing one bar costs the reader
    a bar; raising here costs him the whole page.
    """
    try:
        n = float(valor)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) else None


def barras(rotulos, valores, *, largura: int = 320, altura: int = 180) -> str:
    pares = [(r, n) for r, v in zip(rotulos, valores) if (n := _numero(v)) is not None]
    if not pares:
        return ""

    # The scale always spans at least zero to zero: a chart of only positive
    # values keeps zero pinned to the bottom (today's behaviour, unchanged
    # byte-for-byte); a chart with negative values (e.g. weight lost since the
    # last weighing) gets zero pulled inside the plot area, with bars for
    # negative values hanging downward from it instead of drawing a negative,
    # invisible, out-of-viewBox height.
    valores = [v for _, v in pares]
    minimo = min(0.0, min(valores))
    maximo = max(0.0, max(valores))
    amplitude = (maximo - minimo) or 1.0
    area = altura - MARGEM_BASE
    passo = largura / len(pares)
    corpo = max(passo * 0.6, 1.0)
    linha_zero = area - (0 - minimo) / amplitude * area

    partes = [
        f'<svg viewBox="0 0 {largura} {altura}" width="100%" height="{altura}" '
        f'role="img" class="grafico">'
    ]
    for i, (rotulo, valor) in enumerate(pares):
        h = abs(valor) / amplitude * area
        y_valor = area - (valor - minimo) / amplitude * area
        y = min(linha_zero, y_valor)
        x = i * passo + (passo - corpo) / 2
        partes.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{corpo:.1f}" height="{h:.1f}" rx="2"/>'
        )
        partes.append(
            f'<text x="{i * passo + passo / 2:.1f}" y="{altura - 6}" '
            f'text-anchor="middle" class="rotulo">{escape(str(rotulo))}</text>'
        )
    partes.append("</svg>")
    return "".join(partes)

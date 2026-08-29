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

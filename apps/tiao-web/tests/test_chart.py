import re

from tiao_web.chart import barras

LARGURA_PADRAO = 320
ALTURA_PADRAO = 180


def _retangulos(svg: str) -> list[dict[str, float]]:
    """Parse the numeric attributes off every <rect> in an SVG fragment."""
    campos = ("x", "y", "width", "height")
    return [
        {campo: float(valor) for campo, valor in zip(campos, m.groups())}
        for m in re.finditer(
            r'<rect x="([\d.\-]+)" y="([\d.\-]+)" width="([\d.\-]+)" height="([\d.\-]+)"',
            svg,
        )
    ]


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


def test_serie_toda_positiva_permanece_identica():
    # Golden output captured before the negative-value fix. A series with no
    # negative values must keep producing byte-identical SVG, since Task 4's
    # renderer is covered by golden tests against this output.
    assert barras(["45", "120", "78"], [320, 447, 330]) == (
        '<svg viewBox="0 0 320 180" width="100%" height="180" role="img" '
        'class="grafico"><rect x="21.3" y="44.9" width="64.0" height="113.1" '
        'rx="2"/><text x="53.3" y="174" text-anchor="middle" '
        'class="rotulo">45</text><rect x="128.0" y="0.0" width="64.0" '
        'height="158.0" rx="2"/><text x="160.0" y="174" text-anchor="middle" '
        'class="rotulo">120</text><rect x="234.7" y="41.4" width="64.0" '
        'height="116.6" rx="2"/><text x="266.7" y="174" text-anchor="middle" '
        'class="rotulo">78</text></svg>'
    )


def test_valor_negativo_gera_altura_positiva_dentro_do_viewbox():
    # A view like "ganho de peso desde a última pesagem" is negative for any
    # animal that lost weight. A negative height is invalid SVG: browsers
    # don't paint the rect and the reader silently loses data.
    svg = barras(["a", "b"], [-5, 10])
    retangulos = _retangulos(svg)
    assert len(retangulos) == 2
    for r in retangulos:
        assert r["height"] > 0
        assert r["y"] >= 0
        assert r["y"] + r["height"] <= ALTURA_PADRAO
        assert r["x"] >= 0
        assert r["x"] + r["width"] <= LARGURA_PADRAO


def test_serie_toda_negativa_gera_altura_positiva_dentro_do_viewbox():
    svg = barras(["a", "b"], [-5, -10])
    retangulos = _retangulos(svg)
    assert len(retangulos) == 2
    for r in retangulos:
        assert r["height"] > 0
        assert r["y"] >= 0
        assert r["y"] + r["height"] <= ALTURA_PADRAO


def test_valor_none_e_ignorado():
    svg = barras(["a", "b", "c"], [10, None, 20])
    assert svg.count("<rect") == 2
    assert ">a<" in svg
    assert ">c<" in svg
    assert ">b<" not in svg


def test_valor_nao_numerico_e_ignorado():
    # parse_spec checks that grafico.y names an existing column, not that the
    # column holds numbers, so a legitimate spec can point the chart at a text
    # column. That must cost the reader one bar, not the whole page.
    svg = barras(["a", "b", "c"], [10, "novilha", 20])
    assert svg.count("<rect") == 2
    assert ">a<" in svg
    assert ">c<" in svg
    assert ">b<" not in svg


def test_serie_toda_nao_numerica_nao_gera_svg():
    assert barras(["a", "b"], ["novilha", "boi"]) == ""


def test_nan_e_infinito_sao_ignorados():
    # float() accepts both, but they serialise as "nan"/"inf" in the geometry
    # attributes, which browsers refuse to paint.
    svg = barras(["a", "b", "c"], [10, float("nan"), float("inf")])
    assert svg.count("<rect") == 1
    assert "nan" not in svg.lower()
    assert "inf" not in svg.lower()

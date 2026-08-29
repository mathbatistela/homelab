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

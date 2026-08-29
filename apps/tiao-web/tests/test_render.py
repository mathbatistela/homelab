from tiao_web.render import formatar, render_pagina
from tiao_web.spec import parse_spec

SPEC = parse_spec(
    {
        "titulo": "Pesagem de 21/06/2026",
        "resumo": [{"rotulo": "Cabeças", "valor": "2"}],
        "fonte": {"sql": "SELECT brinco, peso_kg FROM pesagens", "params": {}},
        "tabela": {
            "colunas": [
                {"campo": "brinco", "rotulo": "Brinco"},
                {"campo": "peso_kg", "rotulo": "Peso", "formato": "kg"},
            ]
        },
        "grafico": {"tipo": "barras", "x": "brinco", "y": "peso_kg"},
    }
)
LINHAS = [{"brinco": "367", "peso_kg": 282}, {"brinco": "453", "peso_kg": 284}]


def test_formatar_kg():
    assert formatar(282, "kg") == "282 kg"


def test_formatar_reais():
    assert formatar(2900, "reais") == "R$ 2.900,00"


def test_formatar_data():
    import datetime

    assert formatar(datetime.date(2026, 6, 21), "data") == "21/06/2026"


def test_formatar_vazio_nao_mostra_none():
    assert formatar(None, "kg") == "—"


def test_formatar_kg_com_texto_nao_numerico_cai_para_texto_plano():
    assert formatar("novilha", "kg") == "novilha"


def test_formatar_reais_com_texto_nao_numerico_cai_para_texto_plano():
    assert formatar("novilha", "reais") == "novilha"


def test_formatar_numero_com_texto_nao_numerico_cai_para_texto_plano():
    assert formatar("novilha", "numero") == "novilha"


def test_formatar_numerico_continua_igual_apos_fallback():
    assert formatar(282, "kg") == "282 kg"
    assert formatar(2900, "reais") == "R$ 2.900,00"
    assert formatar(7, "numero") == "7"
    assert formatar(0, "kg") == "0 kg"


def test_pagina_tem_titulo_e_linhas():
    html = render_pagina(SPEC, LINHAS)
    assert "Pesagem de 21/06/2026" in html
    assert "367" in html and "282 kg" in html
    assert html.count("<tr") == 3  # header + 2 rows


def test_pagina_tem_resumo_e_grafico():
    html = render_pagina(SPEC, LINHAS)
    assert "Cabeças" in html
    assert "<svg" in html


def test_estilo_vai_embutido_sem_cdn():
    html = render_pagina(SPEC, LINHAS)
    assert "<style>" in html
    assert "http://" not in html and "https://" not in html


def test_sem_linhas_mostra_recado_em_portugues():
    html = render_pagina(SPEC, [])
    assert "Nada anotado" in html
    assert "<svg" not in html


def test_valor_da_linha_e_escapado():
    html = render_pagina(SPEC, [{"brinco": "<script>", "peso_kg": 1}])
    assert "<script>" not in html
    assert "&lt;script&gt;" in html

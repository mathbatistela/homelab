import datetime
from decimal import Decimal

from tiao_web.views import pesagens, resumir_pesagens


def test_pesagens_monta_spec_valido_com_data():
    s = pesagens("2026-06-21")
    assert s.params == {"data": "2026-06-21"}
    assert "pesagens" in s.sql
    assert [c.campo for c in s.colunas] == ["brinco", "peso_kg", "categoria"]
    assert s.grafico is not None


def test_pesagens_sem_data_usa_hoje():
    s = pesagens(None)
    assert s.params["data"] == datetime.date.today().isoformat()


def test_titulo_e_em_portugues_com_data_legivel():
    s = pesagens("2026-06-21")
    assert s.titulo == "Pesagem de 21/06/2026"


def test_data_invalida_cai_para_hoje():
    s = pesagens("nao-e-data")
    assert s.params["data"] == datetime.date.today().isoformat()


# --- The summary the spec's URL table and worked example both promise ---
# "Cabeças" and "Média" are the line a rancher glances at first. The values
# come from the rows, so they are computed after the query, not at spec time.


def test_resumo_traz_cabecas_e_media():
    s = resumir_pesagens(
        pesagens("2026-06-21"),
        [
            {"brinco": "367", "peso_kg": 282, "categoria": "novilha"},
            {"brinco": "453", "peso_kg": 284, "categoria": "novilha"},
        ],
    )
    assert s.resumo == [
        {"rotulo": "Cabeças", "valor": "2"},
        {"rotulo": "Média", "valor": "283 kg"},
    ]


def test_resumo_conta_todas_as_cabecas_mas_so_pesa_o_que_da():
    s = resumir_pesagens(
        pesagens(None),
        [{"brinco": "1", "peso_kg": None}, {"brinco": "2", "peso_kg": 300}],
    )
    assert s.resumo == [
        {"rotulo": "Cabeças", "valor": "2"},
        {"rotulo": "Média", "valor": "300 kg"},
    ]


def test_resumo_sem_nenhum_peso_mostra_so_cabecas():
    s = resumir_pesagens(pesagens(None), [{"brinco": "1", "peso_kg": None}])
    assert s.resumo == [{"rotulo": "Cabeças", "valor": "1"}]


def test_sem_linhas_nao_tem_resumo():
    # The page already says "Nada anotado por aqui ainda, patrão."
    assert resumir_pesagens(pesagens(None), []).resumo == []


def test_resumo_aceita_decimal_do_banco():
    s = resumir_pesagens(
        pesagens(None),
        [{"peso_kg": Decimal("282.5")}, {"peso_kg": Decimal("283.5")}],
    )
    assert s.resumo[1] == {"rotulo": "Média", "valor": "283 kg"}


def test_resumir_nao_altera_o_resto_da_spec():
    s = pesagens("2026-06-21")
    r = resumir_pesagens(s, [{"brinco": "1", "peso_kg": 300}])
    assert r.sql == s.sql
    assert r.params == s.params
    assert r.titulo == s.titulo
    assert [c.campo for c in r.colunas] == [c.campo for c in s.colunas]

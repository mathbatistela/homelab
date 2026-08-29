import datetime

from tiao_web.views import pesagens


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

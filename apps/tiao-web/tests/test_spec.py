import pytest

from tiao_web.spec import SpecInvalido, parse_spec

BASE = {
    "titulo": "Pesagem de 21/06/2026",
    "fonte": {
        "sql": "SELECT a.brinco, p.peso_kg FROM pesagens p JOIN animais a ON a.id = p.animal_id WHERE p.data = :data",
        "params": {"data": "2026-06-21"},
    },
    "tabela": {
        "colunas": [
            {"campo": "brinco", "rotulo": "Brinco"},
            {"campo": "peso_kg", "rotulo": "Peso", "formato": "kg"},
        ]
    },
}


def test_spec_minimo_e_aceito():
    s = parse_spec(BASE)
    assert s.titulo == "Pesagem de 21/06/2026"
    assert s.params == {"data": "2026-06-21"}
    assert [c.campo for c in s.colunas] == ["brinco", "peso_kg"]
    assert s.colunas[1].formato == "kg"
    assert s.sql.endswith("LIMIT 500")


def test_param_faltando_e_rejeitado():
    dados = {**BASE, "fonte": {"sql": "SELECT 1 WHERE x = :data", "params": {}}}
    with pytest.raises(SpecInvalido, match="data"):
        parse_spec(dados)


def test_param_sobrando_e_rejeitado():
    dados = {**BASE, "fonte": {"sql": "SELECT 1", "params": {"nao_usado": 1}}}
    with pytest.raises(SpecInvalido, match="nao_usado"):
        parse_spec(dados)


def test_sql_de_escrita_e_rejeitado():
    dados = {**BASE, "fonte": {"sql": "DELETE FROM animais", "params": {}}}
    with pytest.raises(SpecInvalido):
        parse_spec(dados)


def test_titulo_obrigatorio():
    dados = {k: v for k, v in BASE.items() if k != "titulo"}
    with pytest.raises(SpecInvalido, match="titulo"):
        parse_spec(dados)


def test_formato_invalido_e_rejeitado():
    dados = {
        **BASE,
        "tabela": {"colunas": [{"campo": "x", "rotulo": "X", "formato": "foguete"}]},
    }
    with pytest.raises(SpecInvalido, match="foguete"):
        parse_spec(dados)


def test_grafico_precisa_de_colunas_existentes():
    dados = {**BASE, "grafico": {"tipo": "barras", "x": "brinco", "y": "inexistente"}}
    with pytest.raises(SpecInvalido, match="inexistente"):
        parse_spec(dados)

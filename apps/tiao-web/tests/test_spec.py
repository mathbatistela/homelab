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


# --- Fix round 1: every rejection must be SpecInvalido, never a raw exception ---
# parse_spec is the trust boundary for model-authored JSON — a wrong type in any
# field must be reported the same way as any other malformed spec.


def test_titulo_tipo_invalido_e_rejeitado():
    dados = {**BASE, "titulo": 123}
    with pytest.raises(SpecInvalido, match="titulo"):
        parse_spec(dados)


def test_tabela_tipo_invalido_e_rejeitada():
    dados = {**BASE, "tabela": "evil"}
    with pytest.raises(SpecInvalido, match="tabela"):
        parse_spec(dados)


def test_fonte_tipo_invalido_e_rejeitada():
    dados = {**BASE, "fonte": ["evil"]}
    with pytest.raises(SpecInvalido, match="fonte"):
        parse_spec(dados)


def test_grafico_tipo_invalido_e_rejeitado():
    dados = {**BASE, "grafico": "evil"}
    with pytest.raises(SpecInvalido, match="grafico"):
        parse_spec(dados)


def test_resumo_tipo_invalido_e_rejeitado():
    dados = {**BASE, "resumo": 5}
    with pytest.raises(SpecInvalido, match="resumo"):
        parse_spec(dados)


def test_colunas_tipo_invalido_e_rejeitada():
    dados = {**BASE, "tabela": {"colunas": "nao e uma lista"}}
    with pytest.raises(SpecInvalido, match="colunas"):
        parse_spec(dados)


def test_coluna_que_nao_e_objeto_e_rejeitada():
    dados = {**BASE, "tabela": {"colunas": ["nao e um objeto"]}}
    with pytest.raises(SpecInvalido):
        parse_spec(dados)


def test_coluna_sem_campo_e_rejeitada():
    dados = {**BASE, "tabela": {"colunas": [{"rotulo": "Sem campo"}]}}
    with pytest.raises(SpecInvalido, match="campo"):
        parse_spec(dados)


def test_coluna_sem_rotulo_e_rejeitada():
    dados = {**BASE, "tabela": {"colunas": [{"campo": "x"}]}}
    with pytest.raises(SpecInvalido, match="rotulo"):
        parse_spec(dados)


def test_resumo_item_sem_rotulo_ou_valor_e_rejeitado():
    dados = {**BASE, "resumo": [{"rotulo": "Total"}]}
    with pytest.raises(SpecInvalido, match="resumo"):
        parse_spec(dados)


def test_resumo_valido_e_aceito():
    dados = {**BASE, "resumo": [{"rotulo": "Total", "valor": "42"}]}
    s = parse_spec(dados)
    assert s.resumo == [{"rotulo": "Total", "valor": "42"}]


# --- Fix round 1: parameter extraction must respect SQL lexical structure ---
# A colon inside a string literal or a comment is not a bind parameter.


def test_literal_de_string_com_dois_pontos_e_aceito():
    dados = {
        **BASE,
        "fonte": {
            "sql": (
                "SELECT a.brinco, p.peso_kg FROM pesagens p "
                "JOIN animais a ON a.id = p.animal_id "
                "WHERE p.categoria = 'Categoria:Bovino' AND p.data = :data"
            ),
            "params": {"data": "2026-06-21"},
        },
    }
    s = parse_spec(dados)
    assert s.params == {"data": "2026-06-21"}


def test_comentario_com_dois_pontos_e_aceito():
    dados = {
        **BASE,
        "fonte": {
            "sql": (
                "SELECT a.brinco, p.peso_kg FROM pesagens p "
                "JOIN animais a ON a.id = p.animal_id "
                "-- filtro por data:aproximada\n"
                "WHERE p.data = :data"
            ),
            "params": {"data": "2026-06-21"},
        },
    }
    s = parse_spec(dados)
    assert s.params == {"data": "2026-06-21"}


def test_cast_de_tipo_e_aceito():
    dados = {
        **BASE,
        "fonte": {
            "sql": "SELECT a.brinco, p.peso_kg::text FROM pesagens p WHERE p.data = :data",
            "params": {"data": "2026-06-21"},
        },
    }
    s = parse_spec(dados)
    assert s.params == {"data": "2026-06-21"}


def test_parametro_genuino_ainda_e_exigido_e_casado():
    dados = {**BASE, "fonte": {"sql": "SELECT 1 WHERE x = :data", "params": {}}}
    with pytest.raises(SpecInvalido, match="data"):
        parse_spec(dados)


# --- Fix round 2: ingest and execution must read the SQL the same way ---
# A hand-written regex read ":data::date" as "data"; SQLAlchemy's text() reads
# it as "dat". A spec therefore passed parse_spec and raised at executar, and
# Seu Jader got "deu uma encrenca" on a link the bot had just sent him.


def test_cast_colado_no_parametro_e_recusado_no_ingest():
    dados = {
        **BASE,
        "fonte": {
            "sql": "SELECT p.peso_kg FROM pesagens p WHERE p.data = :data::date",
            "params": {"data": "2026-06-21"},
        },
    }
    with pytest.raises(SpecInvalido):
        parse_spec(dados)


def test_cast_explicito_do_parametro_e_aceito():
    # CAST(:data AS date) is the form that survives text() intact.
    dados = {
        **BASE,
        "fonte": {
            "sql": "SELECT p.peso_kg FROM pesagens p WHERE p.data = CAST(:data AS date)",
            "params": {"data": "2026-06-21"},
        },
    }
    s = parse_spec(dados)
    assert s.params == {"data": "2026-06-21"}


@pytest.mark.parametrize(
    "sql, params",
    [
        ("SELECT p.peso_kg FROM pesagens p WHERE p.data = :data", {"data": "2026-06-21"}),
        ("SELECT p.peso_kg::text FROM pesagens p WHERE p.data = :data", {"data": "2026-06-21"}),
        (
            "SELECT p.peso_kg FROM pesagens p WHERE p.categoria = 'Categoria:Bovino' "
            "AND p.data = :data",
            {"data": "2026-06-21"},
        ),
        ("SELECT p.peso_kg FROM pesagens p WHERE p.brinco = :brinco AND p.data = :data",
         {"brinco": "367", "data": "2026-06-21"}),
    ],
)
def test_parametros_aceitos_sao_exatamente_os_que_o_driver_vai_ligar(sql, params):
    # The property the fix buys: whatever parse_spec approved is what executar
    # will bind. They cannot drift, because there is only one reader now.
    from sqlalchemy import text

    s = parse_spec({**BASE, "fonte": {"sql": sql, "params": params}})
    assert set(text(s.sql)._bindparams) == set(s.params)

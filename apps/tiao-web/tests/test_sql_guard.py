import pytest

from tiao_web.sql_guard import SqlNaoPermitido, check_sql


def test_select_simples_passa_e_ganha_limit():
    assert check_sql("SELECT brinco FROM animais") == "SELECT brinco FROM animais LIMIT 500"


def test_limit_existente_e_preservado():
    sql = "SELECT brinco FROM animais LIMIT 10"
    assert check_sql(sql) == sql


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO animais (brinco) VALUES ('1')",
        "UPDATE animais SET brinco = '1'",
        "DELETE FROM animais",
        "DROP TABLE animais",
        "ALTER TABLE animais ADD COLUMN x TEXT",
        "TRUNCATE animais",
        "GRANT SELECT ON animais TO x",
        "COPY animais FROM '/tmp/x'",
        "VACUUM animais",
    ],
)
def test_escrita_e_rejeitada(sql):
    with pytest.raises(SqlNaoPermitido):
        check_sql(sql)


@pytest.mark.parametrize(
    "sql, esperado",
    [
        (
            "SELECT total AS truncate FROM animais",
            "SELECT total AS truncate FROM animais LIMIT 500",
        ),
        ("SELECT copy FROM animais", "SELECT copy FROM animais LIMIT 500"),
        ("SELECT vacuum FROM animais", "SELECT vacuum FROM animais LIMIT 500"),
    ],
)
def test_palavra_nao_reservada_como_coluna_ou_alias_e_aceita(sql, esperado):
    # TRUNCATE, COPY e VACUUM nao sao palavras reservadas no PostgreSQL: sao
    # nomes de coluna e apelidos (alias) legitimos.
    assert check_sql(sql) == esperado


def test_multiplas_instrucoes_sao_rejeitadas():
    with pytest.raises(SqlNaoPermitido):
        check_sql("SELECT 1; DROP TABLE animais")


def test_cte_que_escreve_e_rejeitada():
    with pytest.raises(SqlNaoPermitido):
        check_sql("WITH x AS (DELETE FROM animais RETURNING id) SELECT * FROM x")


def test_ponto_e_virgula_final_e_aceito():
    assert check_sql("SELECT 1;") == "SELECT 1 LIMIT 500"

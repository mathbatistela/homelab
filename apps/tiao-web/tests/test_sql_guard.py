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


# --- Fix round 2: 500 is a ceiling, not a default ---
# _tem_limit matched the keyword anywhere in the flattened token stream, so a
# LIMIT inside a subquery counted as "already limited" and a LIMIT 100000 was
# accepted as written. Nothing else caps the result size: statement_timeout is
# advisory (the role can unset it) and the pool is 2 connections deep.


def test_limit_acima_do_teto_e_reduzido():
    assert (
        check_sql("SELECT brinco FROM animais LIMIT 100000")
        == "SELECT brinco FROM animais LIMIT 500"
    )


def test_limit_no_teto_e_preservado():
    sql = "SELECT brinco FROM animais LIMIT 500"
    assert check_sql(sql) == sql


def test_limit_aninhado_nao_vale_como_teto():
    sql = "SELECT * FROM (SELECT brinco FROM animais LIMIT 10) t"
    assert check_sql(sql) == f"{sql} LIMIT 500"


def test_limit_aninhado_grande_ganha_teto_externo():
    sql = "SELECT * FROM (SELECT brinco FROM animais LIMIT 100000) t"
    assert check_sql(sql) == f"{sql} LIMIT 500"


def test_limit_com_offset_mantem_o_offset():
    assert (
        check_sql("SELECT brinco FROM animais ORDER BY brinco LIMIT 900 OFFSET 5")
        == "SELECT brinco FROM animais ORDER BY brinco LIMIT 500 OFFSET 5"
    )


@pytest.mark.parametrize("valor", ["ALL", ":n", "10.5"])
def test_limit_ilegivel_e_tratado_como_ilimitado(valor):
    # Anything we cannot read as an integer within the cap gets the cap.
    # Os tres valores aqui sao tokens simples: sqlparse nao agrupa nenhum deles.
    # Valor agrupado (entre parenteses ou com conta) segue outro caminho — ver
    # test_limit_agrupado_* no fim do arquivo.
    assert (
        check_sql(f"SELECT brinco FROM animais LIMIT {valor}")
        == "SELECT brinco FROM animais LIMIT 500"
    )


def test_teto_configuravel():
    assert check_sql("SELECT brinco FROM animais LIMIT 900", limite=10) == (
        "SELECT brinco FROM animais LIMIT 10"
    )


# --- Fix round 3: a limit the guard cannot rewrite is rejected, not "capped" ---
# The cases above all reach _acima_do_teto as a single ungrouped token, which is
# exactly why they missed this: sqlparse groups a parenthesised or computed
# limit into a TokenList, whose str() comes from its children, so the old
# assignment to .value was a silent no-op and the statement went out uncapped
# while check_sql reported it capped.


@pytest.mark.parametrize("valor", ["(100000)", "100000+1"])
def test_limit_agrupado_acima_do_teto_e_rejeitado(valor):
    with pytest.raises(SqlNaoPermitido):
        check_sql(f"SELECT brinco FROM animais LIMIT {valor}")


def test_limit_agrupado_abaixo_do_teto_tambem_e_rejeitado():
    # Escolha deliberada: LIMIT (10) cabe no teto, mas o guard le numero
    # inteiro simples, nao expressao. Rejeitar vale para todo valor agrupado —
    # uma regra so, sem excecao, e o que mantem o teto verificavel. Quem escreve
    # a spec troca por LIMIT 10.
    with pytest.raises(SqlNaoPermitido):
        check_sql("SELECT brinco FROM animais LIMIT (10)")

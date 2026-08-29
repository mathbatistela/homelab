"""End-to-end checks against the live deployment.

Run explicitly: these talk to the real database and the real public URL.
    cd apps/tiao-web && .venv/bin/python -m pytest e2e/ -v -s

Requires: PIN in TIAO_PIN, bot credentials in the tiao_user PG* vars,
site credentials in TIAO_WEB_PG* vars, all supplied by the runner.
"""

import datetime
import os
import re

import httpx
import psycopg
import pytest

BASE = os.environ.get("TIAO_URL", "https://tiao.batistela.tech")
PIN = os.environ["TIAO_PIN"]
HOJE = datetime.date.today()

BRINCOS = [("e2e-901", 320, "novilha"), ("e2e-902", 447, "boi"), ("e2e-903", 263, "bezerro")]

# Weighed again mid-suite, so it is kept out of BRINCOS: no test asserts its
# weight, and the resend test cannot break one that does.
REENVIO = ("e2e-904", 512, "vaca")

PADRAO = "e2e-90%"

# Every table the ledger has. The site may read all four and write none.
CADERNETA = ("animais", "pesagens", "compras", "compradores")


def _conn(prefix=""):
    return psycopg.connect(
        host=os.environ[f"{prefix}PGHOST"], dbname=os.environ[f"{prefix}PGDATABASE"],
        user=os.environ[f"{prefix}PGUSER"], password=os.environ[f"{prefix}PGPASSWORD"],
        port=os.environ.get(f"{prefix}PGPORT", "5432"),
    )


def _limpar():
    """Remove every e2e row, whoever left it behind."""
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            "DELETE FROM pesagens WHERE animal_id IN "
            "(SELECT id FROM animais WHERE brinco LIKE %s)",
            (PADRAO,),
        )
        cur.execute("DELETE FROM animais WHERE brinco LIKE %s", (PADRAO,))
        c.commit()


@pytest.fixture(scope="module")
def caderneta():
    """Write as the bot writes, then remove every trace.

    The sweep runs before the seed as well as after it, so a run killed halfway
    heals on the next run instead of waiting for someone to read the README.
    """
    _limpar()
    with _conn() as c, c.cursor() as cur:
        for brinco, peso, categoria in [*BRINCOS, REENVIO]:
            cur.execute(
                "INSERT INTO animais (brinco, categoria) VALUES (%s, %s) "
                "ON CONFLICT (brinco) DO NOTHING",
                (brinco, categoria),
            )
            cur.execute(
                "INSERT INTO pesagens (animal_id, data, peso_kg) "
                "SELECT id, %s, %s FROM animais WHERE brinco = %s "
                "ON CONFLICT (animal_id, data) DO UPDATE SET peso_kg = EXCLUDED.peso_kg",
                (HOJE, peso, brinco),
            )
        c.commit()
    yield
    _limpar()


PANGOLIN = os.environ.get("PANGOLIN_URL", "https://pangolin.batistela.tech")
RESOURCE_ID = os.environ.get("TIAO_RESOURCE_ID", "285")


def _pincode(cliente, pin):
    """POST a pincode. A 429 is not an answer, so it stops the run instead of passing as one.

    The gate allows 15 pincode attempts every 15 minutes and answers 429 beyond
    that. A whole run spends two — the wrong PIN and the right one — so hitting
    the ceiling means someone was testing the gate by hand just before. That is
    an operator problem, not a finding: wait out the window and run again.

    It cannot simply be tolerated, though. test_pin_errado_nao_abre only asserts
    that the gate did not answer 200, and a 429 satisfies that: were it allowed
    through, an exhausted quota would turn that test green while proving nothing
    about wrong PINs at all.
    """
    r = cliente.post(
        f"{PANGOLIN}/api/v1/auth/resource/{RESOURCE_ID}/pincode",
        json={"pincode": pin},
        headers={"X-CSRF-Token": "x-csrf-protection"},
    )
    if r.status_code == 429:
        pytest.fail(
            "o Pangolin limitou as tentativas de PIN (15 a cada 15 minutos) e não chegou a "
            f"julgar este PIN. Espere {r.headers.get('retry-after', '?')}s e rode de novo. "
            "Isto não é defeito do portão nem da suíte."
        )
    return r


@pytest.fixture(scope="session")
def sessao():
    """Authenticate to Pangolin's PIN gate exactly as a browser does.

    Three steps, none of them guessable — verified against the live gate:
      1. POST the pincode to the resource's auth endpoint. The
         X-CSRF-Token header is mandatory (403 without it) and its value is a
         literal constant, not something fetched.
      2. Redeem the returned token on the site itself via ?p_session_request=,
         which answers 302 and sets the cookie.
      3. The cookie is named p_session_token_s.<epoch-ms> — per session, so it
         must never be hardcoded. A cookie jar carries it for us.
    """
    cliente = httpx.Client(timeout=30, follow_redirects=False)
    r = _pincode(cliente, PIN)
    r.raise_for_status()
    token = r.json()["data"]["session"]
    cliente.get(f"{BASE}/pesagens", params={"p_session_request": token})
    assert any(c.startswith("p_session_token_s.") for c in cliente.cookies.keys()), \
        "o Pangolin não devolveu o cookie de sessão"
    yield cliente
    cliente.close()


def _get(path, sessao=None):
    """With `sessao`, the PIN gate is satisfied; without it, we are the public."""
    if sessao is None:
        return httpx.get(f"{BASE}{path}", follow_redirects=False, timeout=30)
    return sessao.get(f"{BASE}{path}", follow_redirects=False)


# ── The edge ────────────────────────────────────────────────────────────────

def test_sem_pin_a_caderneta_nao_abre():
    """The one test whose failure stops everything: 200 here means the
    father's ledger is readable by anyone on the internet."""
    r = _get("/pesagens")
    # "not 200" is also satisfied by 502/503/504, so the site being *down*
    # would turn this green. Assert the redirect the gate actually sends.
    assert r.status_code in (302, 307), f"a borda respondeu {r.status_code}, não um desvio ao PIN"
    assert "/auth/resource/" in r.headers.get("location", ""), \
        "o desvio não aponta para o portão do Pangolin"
    corpo = r.text.lower()
    for vazamento in ("brinco", "novilha", "patrão", "pesagem de"):
        assert vazamento not in corpo, f"o corpo não autenticado vazou {vazamento!r}"


def test_pin_errado_nao_abre():
    with httpx.Client(timeout=30, follow_redirects=False) as cliente:
        r = _pincode(cliente, "000000")
    assert r.status_code != 200
    # A 403 (changed CSRF constant), a 404 (renamed endpoint) or a 500 all
    # satisfy the line above without saying anything about PINs. The property
    # an error cannot fake is that no session comes back.
    assert "session" not in (r.json().get("data") or {}), "o PIN errado devolveu uma sessão"


def test_com_pin_a_caderneta_abre(sessao):
    assert _get("/pesagens", sessao).status_code == 200


def test_saude_responde_para_o_pangolin(sessao):
    assert _get("/saude", sessao).status_code == 200


# ── The flow the father actually lives ──────────────────────────────────────

def test_o_que_o_bot_anotou_aparece_na_pagina(caderneta, sessao):
    html = _get(f"/pesagens?data={HOJE.isoformat()}", sessao).text
    for brinco, peso, _ in BRINCOS:
        assert brinco in html, f"o brinco {brinco} não apareceu"
        assert f"{peso} kg" in html, f"o peso de {brinco} não apareceu"


def test_a_pagina_traz_grafico_e_titulo_em_portugues(caderneta, sessao):
    html = _get(f"/pesagens?data={HOJE.isoformat()}", sessao).text
    assert "<svg" in html, "o gráfico não foi desenhado"
    assert f"Pesagem de {HOJE.strftime('%d/%m/%Y')}" in html


def test_um_dia_sem_pesagem_diz_isso_em_portugues(sessao):
    passado = (HOJE - datetime.timedelta(days=3650)).isoformat()
    html = _get(f"/pesagens?data={passado}", sessao).text
    assert "Nada anotado" in html
    assert "<svg" not in html


def test_reenviar_a_mesma_pesagem_nao_duplica(caderneta, sessao):
    """The father resends a photo when the corral signal drops.

    It reweighs e2e-904, which no other test reads, so a failure here points at
    the ON CONFLICT clause rather than at whatever happened to run first.
    """
    brinco = REENVIO[0]
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            "INSERT INTO pesagens (animal_id, data, peso_kg) "
            "SELECT id, %s, %s FROM animais WHERE brinco = %s "
            "ON CONFLICT (animal_id, data) DO UPDATE SET peso_kg = EXCLUDED.peso_kg",
            (HOJE, 999, brinco),
        )
        c.commit()
        cur.execute(
            "SELECT count(*) FROM pesagens p JOIN animais a ON a.id = p.animal_id "
            "WHERE a.brinco = %s AND p.data = %s",
            (brinco, HOJE),
        )
        assert cur.fetchone()[0] == 1, "a pesagem duplicou"
    assert "999 kg" in _get(f"/pesagens?data={HOJE.isoformat()}", sessao).text


# ── Nothing technical ever reaches him ──────────────────────────────────────

def test_caminho_errado_responde_em_portugues(sessao):
    r = _get("/caderneta-que-nao-existe", sessao)
    assert r.status_code == 404
    for palavra in ("Not Found", "Traceback", "Error", "Exception"):
        assert palavra not in r.text
    assert "patrão" in r.text


def test_nenhuma_pagina_vaza_detalhe_tecnico(caderneta, sessao):
    r = _get(f"/pesagens?data={HOJE.isoformat()}", sessao)
    assert r.status_code == 200, "sem a página, não haveria vazamento nenhum a encontrar"
    html = r.text
    for vazamento in ("psycopg", "Traceback", "192.168.", "postgresql://", "SELECT ", "tiao_web_user"):
        assert vazamento not in html, f"a página vazou {vazamento!r}"


def test_a_pagina_nao_depende_de_nada_externo(caderneta, sessao):
    r = _get(f"/pesagens?data={HOJE.isoformat()}", sessao)
    assert r.status_code == 200, "sem a página, não haveria recurso externo a encontrar"
    html = r.text
    assert not re.search(r'(src|href)\s*=\s*["\']https?://', html), \
        "a página busca um recurso externo; falharia no sinal da fazenda"


# ── The site cannot touch the ledger ────────────────────────────────────────

def test_o_site_nao_consegue_escrever():
    """Two independent guards, each asserted on its own.

    psycopg.errors.Error would have been the wrong net: it is the base class of
    every database error, so a missing table or a wrong TIAO_WEB_PGDATABASE
    would satisfy it and this test would pass while proving nothing.

    The refused INSERT arrives as ReadOnlySqlTransaction (25006), not as a
    privilege error: the role runs with default_transaction_read_only, which
    trips before privileges are ever consulted. That alone is a thin proof — a
    session setting is not a grant — so the grants are checked directly too,
    across all four tables of the ledger. pesagens is the one that matters most:
    it holds the weights, and a widened grant there would let the site write the
    father's weighings with nothing else in the suite noticing.
    """
    with _conn("TIAO_WEB_") as c, c.cursor() as cur:
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            cur.execute("INSERT INTO animais (brinco) VALUES ('e2e-invasor')")

    with _conn("TIAO_WEB_") as c, c.cursor() as cur:
        # 25006 is also what a hot standby raises, so the refusal above would
        # look identical on a replica of a role that writes freely on the
        # primary. Rule that reading out before trusting it.
        cur.execute("SELECT pg_is_in_recovery()")
        assert cur.fetchone()[0] is False, \
            "isto é uma réplica: a recusa acima não prova nada sobre o primário"

        # has_table_privilege reports table-level grants only: an INSERT granted
        # on a single column would still read False here.
        for tabela in CADERNETA:
            cur.execute(
                "SELECT has_table_privilege(%s, 'INSERT'), has_table_privilege(%s, 'UPDATE'), "
                "has_table_privilege(%s, 'DELETE'), has_table_privilege(%s, 'SELECT')",
                (tabela, tabela, tabela, tabela),
            )
            insere, atualiza, apaga, le = cur.fetchone()
            assert not (insere or atualiza or apaga), \
                f"o site tem permissão de escrita em {tabela}"
            assert le, f"o site perdeu a permissão de leitura em {tabela}"


def test_o_site_nao_consegue_escrever_por_funcao():
    """42501 exactly: an UndefinedFunction would mean the probe missed, not that
    the door is shut."""
    for sql in ("SELECT setval('animais_id_seq', 1)", "SELECT lo_import('/etc/passwd')"):
        with _conn("TIAO_WEB_") as c, c.cursor() as cur:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur.execute(sql)


def test_o_bot_continua_dono_da_caderneta():
    with _conn() as c, c.cursor() as cur:
        cur.execute("SELECT current_user")
        assert cur.fetchone()[0] == "tiao_user"

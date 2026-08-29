"""End-to-end checks against the live deployment.

Run explicitly: these talk to the real database and the real public URL.
    cd apps/tiao-web && .venv/bin/python -m pytest e2e/ -v -s

Requires: PIN in TIAO_PIN, bot credentials in the tiao_user PG* vars,
site credentials in TIAO_WEB_PG* vars, all supplied by the runner.
"""

import datetime
import os
import re
import time

import httpx
import psycopg
import pytest

BASE = os.environ.get("TIAO_URL", "https://tiao.batistela.tech")
PIN = os.environ["TIAO_PIN"]
HOJE = datetime.date.today()

BRINCOS = [("e2e-901", 320, "novilha"), ("e2e-902", 447, "boi"), ("e2e-903", 263, "bezerro")]


def _conn(prefix=""):
    return psycopg.connect(
        host=os.environ[f"{prefix}PGHOST"], dbname=os.environ[f"{prefix}PGDATABASE"],
        user=os.environ[f"{prefix}PGUSER"], password=os.environ[f"{prefix}PGPASSWORD"],
    )


@pytest.fixture(scope="module")
def caderneta():
    """Write as the bot writes, then remove every trace."""
    with _conn() as c, c.cursor() as cur:
        for brinco, peso, categoria in BRINCOS:
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
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            "DELETE FROM pesagens WHERE animal_id IN "
            "(SELECT id FROM animais WHERE brinco = ANY(%s))",
            ([b for b, _, _ in BRINCOS],),
        )
        cur.execute("DELETE FROM animais WHERE brinco = ANY(%s)", ([b for b, _, _ in BRINCOS],))
        c.commit()


PANGOLIN = os.environ.get("PANGOLIN_URL", "https://pangolin.batistela.tech")
RESOURCE_ID = os.environ.get("TIAO_RESOURCE_ID", "285")

# The gate allows 15 pincode attempts every 15 minutes and answers 429 with a
# Retry-After beyond that. Long enough to sit out a full window, since a whole
# run spends only two attempts.
ESPERA_LIMITE = int(os.environ.get("TIAO_ESPERA_LIMITE", "900"))


def _pincode(cliente, pin):
    """POST a pincode, waiting out the gate's limiter instead of reading it as an answer.

    A 429 says nothing about whether the PIN is right, so accepting one would
    let test_pin_errado_nao_abre pass while proving nothing.
    """
    prazo = time.monotonic() + ESPERA_LIMITE
    while True:
        r = cliente.post(
            f"{PANGOLIN}/api/v1/auth/resource/{RESOURCE_ID}/pincode",
            json={"pincode": pin},
            headers={"X-CSRF-Token": "x-csrf-protection"},
        )
        if r.status_code != 429:
            return r
        espera = int(r.headers.get("retry-after", 60)) + 1
        if time.monotonic() + espera > prazo:
            pytest.fail(
                f"o Pangolin segue limitando as tentativas de PIN depois de {ESPERA_LIMITE}s"
            )
        print(f"\no Pangolin limitou as tentativas de PIN; esperando {espera}s")
        time.sleep(espera)


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
    assert r.status_code != 200, "a caderneta está aberta na internet sem PIN"
    corpo = r.text.lower()
    for vazamento in ("brinco", "novilha", "patrão", "pesagem de"):
        assert vazamento not in corpo, f"o corpo não autenticado vazou {vazamento!r}"


def test_pin_errado_nao_abre():
    with httpx.Client(timeout=30, follow_redirects=False) as cliente:
        r = _pincode(cliente, "000000")
    assert r.status_code != 200


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
    """The father resends a photo when the corral signal drops."""
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            "INSERT INTO pesagens (animal_id, data, peso_kg) "
            "SELECT id, %s, %s FROM animais WHERE brinco = %s "
            "ON CONFLICT (animal_id, data) DO UPDATE SET peso_kg = EXCLUDED.peso_kg",
            (HOJE, 999, "e2e-901"),
        )
        c.commit()
        cur.execute(
            "SELECT count(*) FROM pesagens p JOIN animais a ON a.id = p.animal_id "
            "WHERE a.brinco = %s AND p.data = %s",
            ("e2e-901", HOJE),
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
    html = _get(f"/pesagens?data={HOJE.isoformat()}", sessao).text
    for vazamento in ("psycopg", "Traceback", "192.168.", "postgresql://", "SELECT ", "tiao_web_user"):
        assert vazamento not in html, f"a página vazou {vazamento!r}"


def test_a_pagina_nao_depende_de_nada_externo(caderneta, sessao):
    html = _get(f"/pesagens?data={HOJE.isoformat()}", sessao).text
    assert not re.search(r'(src|href)\s*=\s*["\']https?://', html), \
        "a página busca um recurso externo; falharia no sinal da fazenda"


# ── The site cannot touch the ledger ────────────────────────────────────────

def test_o_site_nao_consegue_escrever():
    with _conn("TIAO_WEB_") as c, c.cursor() as cur:
        with pytest.raises(psycopg.errors.Error):
            cur.execute("INSERT INTO animais (brinco) VALUES ('e2e-invasor')")


def test_o_site_nao_consegue_escrever_por_funcao():
    for sql in ("SELECT setval('animais_id_seq', 1)", "SELECT lo_import('/etc/passwd')"):
        with _conn("TIAO_WEB_") as c, c.cursor() as cur:
            with pytest.raises(psycopg.errors.Error):
                cur.execute(sql)


def test_o_bot_continua_dono_da_caderneta():
    with _conn() as c, c.cursor() as cur:
        cur.execute("SELECT current_user")
        assert cur.fetchone()[0] == "tiao_user"

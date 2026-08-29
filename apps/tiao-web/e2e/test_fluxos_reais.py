"""End-to-end checks against the live deployment.

Run explicitly: these talk to the real database and the real public URL.
    cd apps/tiao-web && .venv/bin/python -m pytest e2e/ -v -s

Requires: PIN in TIAO_PIN, bot credentials in the tiao_user PG* vars,
site credentials in TIAO_WEB_PG* vars, all supplied by the runner.
"""

import datetime
import json
import os
import re
import socket
from urllib.parse import urlparse

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

# The same animal on two different days. The ledger's whole point is weight over
# time, and every other test here reads a single day: a page that answered with
# today's row whatever date was asked would pass all of them.
ONTEM = HOJE - datetime.timedelta(days=1)
HISTORICO = ("e2e-901", 300)  # ontem 300 kg; hoje, na lista acima, 320 kg

# Written and rolled back by the ownership probe. It should never reach disk,
# so nothing reads it — it is listed only so a failed rollback still gets swept.
SONDA = "e2e-909-sonda"

# Every brinco this suite may ever create, named one by one. A LIKE pattern
# would have swept whatever else in Seu Jader's ledger happened to match it.
TODOS_BRINCOS = [b for b, _, _ in BRINCOS] + [REENVIO[0], SONDA]

# Every table the ledger has. The site may read all four and write none.
CADERNETA = ("animais", "pesagens", "compras", "compradores")


def _conn(prefix=""):
    return psycopg.connect(
        host=os.environ[f"{prefix}PGHOST"], dbname=os.environ[f"{prefix}PGDATABASE"],
        user=os.environ[f"{prefix}PGUSER"], password=os.environ[f"{prefix}PGPASSWORD"],
        port=os.environ.get(f"{prefix}PGPORT", "5432"),
    )


def _limpar():
    """Remove every e2e row, whoever left it behind.

    Named brincos, never a pattern: this DELETE runs as the bot, against the
    tables Seu Jader's real ledger lives in, and nothing here needs a wildcard.
    A widened pattern — or a real animal one day tagged close enough to match
    one — would take his rows with ours and nothing would notice.
    """
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            "DELETE FROM pesagens WHERE animal_id IN "
            "(SELECT id FROM animais WHERE brinco = ANY(%s))",
            (TODOS_BRINCOS,),
        )
        cur.execute("DELETE FROM animais WHERE brinco = ANY(%s)", (TODOS_BRINCOS,))
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
        cur.execute(
            "INSERT INTO pesagens (animal_id, data, peso_kg) "
            "SELECT id, %s, %s FROM animais WHERE brinco = %s "
            "ON CONFLICT (animal_id, data) DO UPDATE SET peso_kg = EXCLUDED.peso_kg",
            (ONTEM, HISTORICO[1], HISTORICO[0]),
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


def _linhas(html):
    """The table's data rows, each as its list of cells."""
    linhas = []
    for tr in re.findall(r"<tr>(.*?)</tr>", html, re.S):
        celulas = re.findall(r"<td>(.*?)</td>", tr, re.S)
        if celulas:
            linhas.append([c.strip() for c in celulas])
    return linhas


def _linha(html, brinco):
    """The one row for this animal.

    `f"{peso} kg" in html` is the assertion this replaces, and it passes on a
    page where that weight belongs to one of Seu Jader's real animals while ours
    shows something else entirely. Reading the animal's own row cannot.
    """
    for celulas in _linhas(html):
        if celulas[0] == brinco:
            return celulas
    raise AssertionError(f"o brinco {brinco} não apareceu na tabela")


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


def test_o_portao_recebe_o_pai_em_portugues():
    """The entry point Seu Jader actually uses: he taps the link and lands here.

    Every other test in this file authenticates against Pangolin's JSON API,
    which he never touches. A login page that answers 5xx, comes back blank, or
    offers him a method he has no way to complete would leave him on a dead
    screen with the whole suite still green.

    Fetched the way his phone fetches it — following the redirect and asking for
    Portuguese, because Pangolin picks the language from Accept-Language.
    """
    r = httpx.get(
        f"{BASE}/pesagens",
        follow_redirects=True,
        timeout=30,
        headers={"Accept-Language": "pt-BR,pt;q=0.9"},
    )
    assert r.status_code == 200, f"o portão respondeu {r.status_code} a quem só clicou no link"
    assert "/auth/resource/" in str(r.url), f"o link não terminou no portão: {r.url}"
    assert "text/html" in r.headers.get("content-type", ""), "o portão não devolveu uma página"

    html = r.text
    assert re.search(r'<html[^>]*\slang="pt', html), \
        "o portão respondeu numa língua que não é português"

    # The page renders on the client: the <input> is not in this HTML. What is in
    # it is the payload the component renders from, and that is the only
    # server-side evidence that a PIN prompt, not an error boundary, is what he
    # gets. A browser is what it would take to assert the rendered keypad; short
    # of that, an empty or errored payload is what this catches.
    plano = html.replace('\\"', '"')
    metodos = re.search(r'"methods":(\{[^}]*\})', plano)
    assert metodos, "a página não trouxe o componente de autenticação"
    metodos = json.loads(metodos.group(1))
    assert metodos.get("pincode") is True, "o portão parou de oferecer PIN a ele"
    for outro in ("password", "sso", "whitelist"):
        assert metodos.get(outro) is False, \
            f"o portão está pedindo {outro}, que ele não tem como fazer"

    nome = re.search(r'"resource":\{"name":"([^"]+)"', plano)
    assert nome and "Caderneta" in nome.group(1), \
        "a página não diz qual caderneta ele está abrindo"
    assert '"pincodeSubmit":"' in plano, "a página não traz o texto do botão de entrar"

    for encrenca in ("Application error", "Internal Server Error", "Traceback"):
        assert encrenca not in html, f"o portão mostrou {encrenca!r} para ele"


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
    for brinco, peso, categoria in BRINCOS:
        assert _linha(html, brinco) == [brinco, f"{peso} kg", categoria], \
            f"a linha de {brinco} não trouxe o que o bot anotou"


def test_cada_dia_mostra_o_peso_daquele_dia(caderneta, sessao):
    """The same animal, weighed yesterday and again today.

    This is the ledger's reason to exist — the weight of an animal over time,
    which is also what any "quanto engordou desde a última pesagem" view will be
    built on. Every other test here reads a single day, so a page that ignored
    ?data= and always answered with today's rows would pass all of them.
    """
    brinco, peso_de_ontem = HISTORICO
    peso_de_hoje = next(p for b, p, _ in BRINCOS if b == brinco)
    assert peso_de_ontem != peso_de_hoje, "os dois dias precisam pesar diferente"

    ontem = _get(f"/pesagens?data={ONTEM.isoformat()}", sessao).text
    hoje = _get(f"/pesagens?data={HOJE.isoformat()}", sessao).text

    assert _linha(ontem, brinco)[1] == f"{peso_de_ontem} kg", \
        "a página de ontem não trouxe o peso de ontem"
    assert _linha(hoje, brinco)[1] == f"{peso_de_hoje} kg", \
        "a página de hoje não trouxe o peso de hoje"
    assert f"Pesagem de {ONTEM.strftime('%d/%m/%Y')}" in ontem, \
        "a página de ontem se intitula outro dia"


def test_a_pagina_traz_grafico_e_titulo_em_portugues(caderneta, sessao):
    """`"<svg" in html` was the old assertion, and an empty chart satisfies it:
    the tag opens before the first bar is drawn. Count the bars instead.

    One `<rect>` per row is the property, not one per e2e animal: on the day
    this runs Seu Jader may have weighed his own herd, and those animals belong
    on the same chart.
    """
    html = _get(f"/pesagens?data={HOJE.isoformat()}", sessao).text
    linhas = _linhas(html)
    barras = html.count("<rect")
    assert linhas, "a tabela veio vazia; não havia gráfico a desenhar"
    assert barras, "o gráfico abriu o <svg> e não desenhou barra nenhuma"
    assert barras == len(linhas), \
        f"o gráfico tem {barras} barras para {len(linhas)} animais na tabela"
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
    """`SELECT current_user` was the old assertion, and on a connection opened
    as tiao_user it cannot come back anything else: the test could only fail by
    failing to connect at all.

    What it was written to guard is the vault password rewrite — the hazard that
    a redeploy hands the ledger to another role, or leaves the bot unable to
    write to tables it no longer owns. Ownership is what can actually change
    underneath us, and the write it grants is what the whole ledger rests on.
    """
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            "SELECT tablename, tableowner FROM pg_tables "
            "WHERE schemaname = 'public' AND tablename = ANY(%s)",
            (list(CADERNETA),),
        )
        donos = dict(cur.fetchall())
        assert set(donos) == set(CADERNETA), \
            f"sumiram tabelas da caderneta: {sorted(set(CADERNETA) - set(donos))}"
        for tabela, dono in sorted(donos.items()):
            assert dono == "tiao_user", f"{tabela} agora é de {dono}, não do bot"

        # Ownership on paper with the write refused in practice would still
        # leave the bot mute. Rolled back: nothing of this reaches the ledger.
        cur.execute(
            "INSERT INTO animais (brinco, categoria) VALUES (%s, %s)", (SONDA, "novilha")
        )
        assert cur.rowcount == 1, "o bot não conseguiu mais escrever na caderneta"
        c.rollback()

    with _conn() as c, c.cursor() as cur:
        cur.execute("SELECT count(*) FROM animais WHERE brinco = %s", (SONDA,))
        assert cur.fetchone()[0] == 0, "a sonda de escrita ficou gravada na caderneta"


# ── The doors on the VM ─────────────────────────────────────────────────────

LAN = os.environ.get("TIAO_LAN_IP", "192.168.1.111")
PORTA_LEITURA = int(os.environ.get("TIAO_PORTA_LEITURA", "8790"))
PORTA_ESCRITA = int(os.environ.get("TIAO_PORTA_ESCRITA", "8791"))


def _atende(host, porta, timeout=5):
    """Whether anything accepts a TCP connection there. A refusal and a dropped
    packet are the same answer to us: nobody is listening within reach."""
    try:
        with socket.create_connection((host, porta), timeout=timeout):
            return True
    except OSError:
        return False


def test_as_portas_estao_onde_o_plano_mandou():
    """The read port on the LAN, the write port on loopback, neither in public.

    This is the one test here that has to run from the ranch network: it opens
    sockets to the VM directly instead of going through the tunnel. The read
    port answering is checked first, so a run from the wrong network fails
    saying so rather than passing three silent 'nothing is listening' checks.

    The write port is unused until phase 3, which is exactly why it is worth
    asserting now: nothing else would notice it being published wide.
    """
    try:
        r = httpx.get(f"http://{LAN}:{PORTA_LEITURA}/saude", timeout=10)
    except httpx.HTTPError as exc:
        pytest.fail(
            f"{LAN}:{PORTA_LEITURA} não atendeu ({type(exc).__name__}). Ou o contêiner "
            "caiu, ou esta máquina não está na rede da fazenda — este é o único teste "
            "da suíte que precisa da LAN."
        )
    assert r.status_code == 200, f"a porta de leitura respondeu {r.status_code} na LAN"
    assert r.json() == {"status": "ok"}

    assert not _atende(LAN, PORTA_ESCRITA), (
        f"{LAN}:{PORTA_ESCRITA} atende na LAN; a porta de escrita só pode existir "
        "no loopback da VM"
    )

    # The address the father's own link resolves to. Both ports must be
    # unreachable there: the internet comes in through Pangolin and the PIN, or
    # it does not come in.
    publico = socket.gethostbyname(urlparse(BASE).hostname)
    for porta in (PORTA_LEITURA, PORTA_ESCRITA):
        assert not _atende(publico, porta), \
            f"a porta {porta} atende em {publico}, que é a ponta pública"


import pytest
from starlette.testclient import TestClient

import tiao_web.app as modulo


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setattr(
        modulo, "executar", lambda s: [{"brinco": "367", "peso_kg": 282, "categoria": "novilha"}]
    )
    return TestClient(modulo.app)


def test_saude_responde_ok(cliente):
    r = cliente.get("/saude")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_pesagens_renderiza_html(cliente):
    r = cliente.get("/pesagens?data=2026-06-21")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Pesagem de 21/06/2026" in r.text
    assert "367" in r.text and "282 kg" in r.text


def test_falha_de_banco_mostra_recado_de_peao(cliente, monkeypatch):
    def explode(_s):
        raise RuntimeError("connection refused to 192.168.1.103")

    monkeypatch.setattr(modulo, "executar", explode)
    r = cliente.get("/pesagens")
    assert r.status_code == 200
    assert "deu uma encrenca" in r.text.lower()
    assert "192.168.1.103" not in r.text
    assert "RuntimeError" not in r.text


def test_caminho_desconhecido_mostra_recado_em_portugues(cliente):
    r = cliente.get("/nao-existe")
    assert r.status_code == 404
    assert "text/html" in r.headers["content-type"]
    assert "não achei essa página" in r.text.lower()
    assert "not found" not in r.text.lower()
    assert "404" not in r.text


def test_rotas_existentes_nao_sao_afetadas_pelo_recado_de_404(cliente):
    r_saude = cliente.get("/saude")
    assert r_saude.status_code == 200
    assert r_saude.json() == {"status": "ok"}

    r_pesagens = cliente.get("/pesagens?data=2026-06-21")
    assert r_pesagens.status_code == 200
    assert "text/html" in r_pesagens.headers["content-type"]
    assert "Pesagem de 21/06/2026" in r_pesagens.text


def test_falha_no_render_mostra_recado_de_peao(cliente, monkeypatch):
    # render_pagina used to sit outside the guarded block, so anything it
    # raised became Starlette's English "Internal Server Error".
    def explode(_s, _linhas):
        raise ValueError("could not convert string to float: 'novilha'")

    monkeypatch.setattr(modulo, "render_pagina", explode)
    r = cliente.get("/pesagens")
    assert r.status_code == 200
    assert "deu uma encrenca" in r.text.lower()
    assert "novilha" not in r.text
    assert "internal server error" not in r.text.lower()


def test_erro_fora_do_bloco_guardado_mostra_recado_em_portugues(monkeypatch):
    # Anything raised before the guard (building the spec, for instance) still
    # has to reach Seu Jader in Portuguese.
    def explode(_data):
        raise RuntimeError("boom")

    monkeypatch.setitem(modulo.NOMEADAS, "pesagens", explode)
    cliente = TestClient(modulo.app, raise_server_exceptions=False)
    r = cliente.get("/pesagens")
    assert r.status_code == 500
    assert "text/html" in r.headers["content-type"]
    assert "deu uma encrenca" in r.text.lower()
    assert "internal server error" not in r.text.lower()
    assert "boom" not in r.text


# --- The two pages the reader sees when something already went wrong are the
# --- two that most need to look like the caderneta he knows.


def test_recado_de_erro_usa_a_folha_de_estilo_da_caderneta(cliente, monkeypatch):
    def explode(_s):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(modulo, "executar", explode)
    r = cliente.get("/pesagens")
    assert "prefers-color-scheme" in r.text  # dark mode, only estilo.css has it
    assert "--papel" in r.text
    assert "style=" not in r.text  # no page-local font declaration
    assert "deu uma encrenca" in r.text.lower()


def test_recado_de_caminho_desconhecido_usa_a_folha_de_estilo_da_caderneta(cliente):
    r = cliente.get("/nao-existe")
    assert "prefers-color-scheme" in r.text
    assert "--papel" in r.text
    assert "style=" not in r.text
    assert "não achei essa página" in r.text.lower()

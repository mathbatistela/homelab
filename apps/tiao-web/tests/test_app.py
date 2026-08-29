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

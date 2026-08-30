"""Regressions for the two bugs that made the site useless to Jader in practice.

Both survived a suite of 120 unit tests and 17 e2e flows, because every one of
those asserted a status code. A 200 is satisfied by an empty page and by a
branded 404 alike. These tests assert CONTENT.
"""

import datetime
import types

import pytest
from starlette.testclient import TestClient

import tiao_web.app as app_mod
import tiao_web.views as views


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setattr(
        app_mod, "executar",
        lambda s: [{"brinco": "367", "peso_kg": 282, "categoria": "novilha"}],
    )
    return TestClient(app_mod.app)


def test_raiz_serve_a_pagina_em_vez_de_404(cliente):
    """Jader types the bare domain. It used to answer 404.

    Asserting the status alone would have passed against the old 404 page too,
    which rendered a styled "Caderneta" document -- so assert the data.
    """
    r = cliente.get("/")
    assert r.status_code == 200
    assert "367" in r.text, "a página não trouxe o animal"
    assert "<table" in r.text, "a página não trouxe tabela"


def test_raiz_e_pesagens_servem_a_mesma_pagina(cliente):
    assert cliente.get("/").text == cliente.get("/pesagens").text


def _congelar(monkeypatch, instante_utc):
    """Freezes the clock AND puts the fake server in UTC.

    The second half is what makes these tests real. A first version of this
    helper left `date` as the genuine class, so `date.today()` answered with the
    developer's own machine -- which sits in Sao Paulo. The timezone tests then
    passed against the buggy code and would only have failed in CI. Faking the
    clock but not the server's zone tests nothing here.
    """
    class _DT:
        @staticmethod
        def now(tz=None):
            return instante_utc.astimezone(tz) if tz else instante_utc.replace(tzinfo=None)

    class _Date(datetime.date):
        @classmethod
        def today(cls):
            return instante_utc.date()   # o container roda em UTC

    monkeypatch.setattr(
        views, "datetime",
        types.SimpleNamespace(datetime=_DT, date=_Date),
    )


def test_dia_padrao_e_o_da_fazenda_nao_o_do_servidor(monkeypatch):
    """22:21 in Sao Paulo is already the next day in UTC.

    This is the exact instant the bug was caught in production: the container
    said 30/08, the weighings were dated 29/08, and the page came back empty.
    """
    _congelar(monkeypatch, datetime.datetime(2026, 8, 30, 1, 21,
                                             tzinfo=datetime.timezone.utc))
    assert views._data_valida(None) == datetime.date(2026, 8, 29)


def test_dia_padrao_correto_tambem_de_manha(monkeypatch):
    """Guards the fix from over-correcting: before 21:00 both zones agree."""
    _congelar(monkeypatch, datetime.datetime(2026, 8, 29, 17, 0,
                                             tzinfo=datetime.timezone.utc))
    assert views._data_valida(None) == datetime.date(2026, 8, 29)


def test_data_explicita_continua_mandando(monkeypatch):
    _congelar(monkeypatch, datetime.datetime(2026, 8, 30, 1, 21,
                                             tzinfo=datetime.timezone.utc))
    assert views._data_valida("2026-08-01") == datetime.date(2026, 8, 1)

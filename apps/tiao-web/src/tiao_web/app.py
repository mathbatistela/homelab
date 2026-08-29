"""HTTP surface.

Read routes only in phase 1. There is no login here on purpose: Pangolin checks
the PIN at the edge, before a request reaches this VM.
"""

import logging

from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route

from .db import executar
from .render import render_pagina, render_recado
from .views import NOMEADAS, resumir_pesagens

logger = logging.getLogger("tiao_web")

# Wording only. These go through render_recado like every other page, so one
# renderer keeps deciding how the caderneta looks — most of all on the two
# screens the reader reaches when something has already gone wrong.
RECADO_ERRO = (
    "Ih, patrão, deu uma encrenca aqui pra abrir a caderneta. Tenta de novo daqui a pouco."
)

RECADO_CAMINHO_DESCONHECIDO = (
    "Ih, patrão, não achei essa página aqui na caderneta. Confere se o link que "
    "te mandaram tá certinho, ou pede pra mandar de novo."
)

RECADO_REGISTRO_NAO_ENCONTRADO = "Ih, patrão, isso aí eu não tenho anotado na caderneta."


class RegistroNaoEncontrado(HTTPException):
    """The URL is fine; the thing it names is not in the ledger.

    Both cases are HTTP 404 and the handler is keyed on the status code, so
    without this a route raising HTTPException(404) for an ear tag nobody ever
    wrote down would be answered "não achei essa página" — sending Seu Jader off
    to check a link that was correct all along. A route raises this instead and
    says what is actually missing: "esse brinco eu não achei não".
    """

    def __init__(self, recado: str = RECADO_REGISTRO_NAO_ENCONTRADO):
        super().__init__(status_code=404, detail=recado)


async def nao_encontrado(request, exc):
    recado = (
        exc.detail if isinstance(exc, RegistroNaoEncontrado) else RECADO_CAMINHO_DESCONHECIDO
    )
    return HTMLResponse(render_recado(recado), status_code=404)


async def encrenca(request, exc):
    """Last net under every route.

    Without this, anything a route raises outside its own guard reaches Seu
    Jader as Starlette's "Internal Server Error" — English, on a page he cannot
    read, about a problem he cannot act on.
    """
    logger.exception("erro nao tratado", exc_info=exc)
    return HTMLResponse(render_recado(RECADO_ERRO), status_code=500)


async def saude(request):
    return JSONResponse({"status": "ok"})


async def pesagens(request):
    s = NOMEADAS["pesagens"](request.query_params.get("data"))
    try:
        linhas = executar(s)
        pagina = render_pagina(resumir_pesagens(s, linhas), linhas)
    except Exception:
        # Rendering is inside the guard too: a spec whose chart or formato does
        # not match the data it got back fails here, not in the query, and the
        # reader should still get the recado rather than a broken page.
        # The technical detail goes to the log, never to Seu Jader.
        logger.exception("falha ao montar a caderneta")
        return HTMLResponse(render_recado(RECADO_ERRO), status_code=200)
    return HTMLResponse(pagina)


TRATADORES = {404: nao_encontrado, 500: encrenca}

app = Starlette(
    routes=[
        Route("/saude", saude),
        Route("/pesagens", pesagens),
    ],
    exception_handlers=TRATADORES,
)

"""HTTP surface.

Read routes only in phase 1. There is no login here on purpose: Pangolin checks
the PIN at the edge, before a request reaches this VM.
"""

import logging

from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route

from .db import executar
from .render import render_pagina, render_recado
from .views import NOMEADAS

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


async def caminho_desconhecido(request, exc):
    return HTMLResponse(render_recado(RECADO_CAMINHO_DESCONHECIDO), status_code=404)


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
        pagina = render_pagina(s, linhas)
    except Exception:
        # Rendering is inside the guard too: a spec whose chart or formato does
        # not match the data it got back fails here, not in the query, and the
        # reader should still get the recado rather than a broken page.
        # The technical detail goes to the log, never to Seu Jader.
        logger.exception("falha ao montar a caderneta")
        return HTMLResponse(render_recado(RECADO_ERRO), status_code=200)
    return HTMLResponse(pagina)


app = Starlette(
    routes=[
        Route("/saude", saude),
        Route("/pesagens", pesagens),
    ],
    exception_handlers={404: caminho_desconhecido, 500: encrenca},
)

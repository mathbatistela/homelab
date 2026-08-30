"""HTTP surface.

Read routes only in phase 1. There is no login here on purpose: Pangolin checks
the PIN at the edge, before a request reaches this VM.

Spec creation (``POST /specs``) is published on 8791, bound to 127.0.0.1, and
must be a SECOND ASGI app or a second process — never a route added to this one.
Everything this app serves goes out on 8790, which Pangolin exposes to the
internet behind only the PIN; a write route added here would be published there
too, and the write path would stop being loopback-only, which is the whole
boundary the design rests on.
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

RECADO_SO_DE_OLHAR = (
    "Ih, patrão, essa página aqui é só pra olhar. Pra anotar coisa nova na "
    "caderneta, é comigo mesmo, lá na conversa."
)


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


async def so_de_olhar(request, exc):
    """Every page here is read-only, and saying so is part of the caderneta.

    Starlette answers a POST to an existing route with its own bare "Method Not
    Allowed" — English, unstyled, and about a rule Seu Jader never agreed to.
    Registered by status code like the others, so it is the same page.
    """
    return HTMLResponse(render_recado(RECADO_SO_DE_OLHAR), status_code=405)


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


TRATADORES = {404: nao_encontrado, 405: so_de_olhar, 500: encrenca}

app = Starlette(
    routes=[
        Route("/saude", saude),
        # Jader types the bare domain -- he will never type a path. Serving the
        # page at "/" as well as "/pesagens" means the front door is never a
        # 404. Same handler, no redirect: one less hop through the tunnel.
        Route("/", pesagens),
        Route("/pesagens", pesagens),
    ],
    exception_handlers=TRATADORES,
)

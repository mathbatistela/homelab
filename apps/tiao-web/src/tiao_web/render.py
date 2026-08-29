"""Spec + rows -> HTML. The only place that decides how a page looks.

Formatting lives here rather than in the SQL so that a weight renders identically
on every screen, whatever query produced it.
"""

import datetime
from decimal import Decimal
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .chart import barras

TEMPLATES = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(TEMPLATES),
    autoescape=select_autoescape(["html", "j2"]),
)
_estilo = (TEMPLATES / "estilo.css").read_text(encoding="utf-8")


def formatar(valor, formato: str) -> str:
    if valor is None or valor == "":
        return "—"
    if formato == "kg":
        return f"{_num(valor):g} kg"
    if formato == "reais":
        inteiro = f"{_num(valor):,.2f}"
        return "R$ " + inteiro.replace(",", "@").replace(".", ",").replace("@", ".")
    if formato == "data":
        if isinstance(valor, (datetime.date, datetime.datetime)):
            return valor.strftime("%d/%m/%Y")
        return str(valor)
    if formato == "numero":
        return f"{_num(valor):g}"
    return str(valor)


def _num(valor):
    if isinstance(valor, Decimal):
        return float(valor)
    return float(valor) if isinstance(valor, (int, float)) else float(str(valor))


def render_pagina(s, linhas) -> str:
    celulas = [[formatar(linha.get(c.campo), c.formato) for c in s.colunas] for linha in linhas]

    grafico = ""
    if s.grafico and linhas:
        grafico = barras(
            [str(linha.get(s.grafico.x)) for linha in linhas],
            [linha.get(s.grafico.y) for linha in linhas],
        )

    return _env.get_template("pagina.html.j2").render(
        s=s, linhas=linhas, celulas=celulas, grafico=grafico, estilo=_estilo
    )

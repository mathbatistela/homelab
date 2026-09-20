"""Brazilian number formatting.

Django's L10N would mostly do this, but these are used in headline positions
where "R$ 3.691,98" must be exact and unmissable, so the formatting is explicit
rather than locale-dependent.
"""

from django import template

register = template.Library()


@register.filter
def reais(v):
    if v is None:
        return "—"
    return "R$ " + f"{v:,.2f}".translate(str.maketrans(",.", ".,"))


@register.filter
def numero(v, casas=0):
    if v is None:
        return "—"
    return f"{v:,.{int(casas)}f}".translate(str.maketrans(",.", ".,"))


@register.filter
def arrobas(v):
    if v is None:
        return "—"
    return f"{v:.2f} @".replace(".", ",")


@register.filter
def reais_sinal(v):
    """Signed money: gains and losses must be told apart at a glance."""
    if v is None:
        return "—"
    sinal = "+" if v > 0 else ("-" if v < 0 else "")
    corpo = f"{abs(v):,.2f}".translate(str.maketrans(",.", ".,"))
    return f"{sinal}R$ {corpo}"


@register.filter
def classe_ganho(v):
    if v is None or v == 0:
        return ""
    return "ganho" if v > 0 else "perda"

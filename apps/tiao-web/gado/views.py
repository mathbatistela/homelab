"""Jader's side of the site: read-only, big type, made for a phone.

Deliberately not the admin. However well themed an admin is, it is built for
someone who knows what a changelist is. These are four pages that answer four
questions he actually asks.

Nothing here writes. Everything is one query per page plus prefetches.
"""

from django.db.models import Count, Max, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .models import Animal, Contraparte, Cotacao, Movimentacao


def _rebanho_base():
    return (Animal.objects
            .select_related("propriedade", "compra", "venda")
            .prefetch_related("pesagens", "despesas"))


def rebanho(request):
    """The detailed herd list -- the spreadsheet's Animais tab, kept live."""
    propriedade = request.GET.get("propriedade") or ""
    situacao = request.GET.get("situacao") or ""

    animais = _rebanho_base()
    if propriedade:
        animais = animais.filter(propriedade__nome=propriedade)
    if situacao == "pasto":
        animais = animais.filter(venda__isnull=True)
    elif situacao == "vendido":
        animais = animais.filter(venda__isnull=False)
    animais = list(animais)

    valores = [a.valor_atual for a in animais if a.valor_atual is not None]
    return render(request, "gado/rebanho.html", {
        "animais": animais,
        "total_cabecas": len(animais),
        "valor_total": sum(valores) if valores else None,
        "peso_total": sum(a.peso_atual_kg or 0 for a in animais),
        "propriedades": (Animal.objects.exclude(propriedade=None)
                         .values_list("propriedade__nome", flat=True)
                         .distinct().order_by("propriedade__nome")),
        "propriedade_ativa": propriedade,
        "situacao_ativa": situacao,
        "pagina": "rebanho",
    })


def animal(request, brinco):
    """One animal's card: what it is, what it weighs, what it cost, what it's worth."""
    bicho = get_object_or_404(_rebanho_base(), brinco=brinco)
    despesas = list(bicho.despesas.all())
    return render(request, "gado/animal.html", {
        "a": bicho,
        "pesagens": list(reversed(bicho._pesagens_ordenadas)),
        "despesas": sorted(despesas, key=lambda d: d.data, reverse=True),
        "total_despesas": sum(d.valor for d in despesas) if despesas else None,
        "pagina": "rebanho",
    })


def cotacao(request):
    """Today's price for the three categories, plus what it has been doing."""
    ultimas, historico = {}, {}
    for chave, rotulo in Cotacao.CATEGORIAS:
        linhas = list(Cotacao.objects.filter(categoria=chave)
                      .order_by("-data_pregao")[:15])
        if linhas:
            ultimas[rotulo] = linhas[0]
            historico[rotulo] = linhas
    return render(request, "gado/cotacao.html", {
        "ultimas": ultimas,
        "historico": historico,
        "hoje": timezone.localdate(),
        "pagina": "cotacao",
    })


def negocios(request):
    """Purchases and sales, and who was on the other side."""
    movs = (Movimentacao.objects.select_related("comprador").order_by("-data"))
    contrapartes = (Contraparte.objects
                    .annotate(negocios=Count("movimentacoes"),
                              ultimo=Max("movimentacoes__data"),
                              total=Sum("movimentacoes__valor"))
                    .order_by("nome"))
    return render(request, "gado/negocios.html", {
        "compras": [m for m in movs if m.tipo == Movimentacao.COMPRA],
        "vendas": [m for m in movs if m.tipo == Movimentacao.VENDA],
        "contrapartes": contrapartes,
        "pagina": "negocios",
    })


def saude(request):
    """Liveness probe. The app.yml healthcheck points here.

    Touches the database on purpose: a process that is up but cannot reach
    Postgres serves nothing useful, and a probe that only proves the process
    exists would call that healthy.
    """
    try:
        Animal.objects.exists()
    except Exception as e:
        return JsonResponse({"status": "sem banco", "erro": str(e)[:120]}, status=503)
    return JsonResponse({"status": "ok"})

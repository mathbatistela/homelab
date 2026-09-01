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
    animais = Animal.com_cotacoes(animais)

    # Sold animals are excluded from the herd's worth: they are no longer his,
    # and counting what they "would be worth today" inflates the total with
    # cattle that left the farm.
    no_pasto = [a for a in animais if not a.vendido]
    valores = [a.valor_atual for a in no_pasto if a.valor_atual is not None]
    custos = [a.custo_total for a in no_pasto if a.custo_total is not None]
    ganhos = [a.ganho for a in no_pasto if a.ganho is not None]
    return render(request, "gado/rebanho.html", {
        "animais": animais,
        "total_cabecas": len(no_pasto),
        "total_vendidas": len(animais) - len(no_pasto),
        "valor_total": sum(valores) if valores else None,
        "custo_total": sum(custos) if custos else None,
        "ganho_total": sum(ganhos) if ganhos else None,
        "peso_total": sum(a.peso_atual_kg or 0 for a in no_pasto),
        "propriedades": (Animal.objects.exclude(propriedade=None)
                         .values_list("propriedade__nome", flat=True)
                         .distinct().order_by("propriedade__nome")),
        "propriedade_ativa": propriedade,
        "situacao_ativa": situacao,
        "pagina": "rebanho",
    })


def _acoes_tiao(a):
    """The handful of things he actually does to an animal, ready to send.

    An empty message box asks a 70-year-old to compose a sentence on a phone
    keyboard. These leave him a number to type instead. The wording is his, not
    the system's -- "pesei", "mudei de pasto", "vendi".

    Gaps come first when there are any: the page already knows what the record
    is missing, so it may as well offer to fill it.
    """
    quem = a.como_falar
    acoes = []

    # O que falta vem primeiro -- é o que o sistema sabe que precisa.
    if not a.categoria:
        acoes.append(("Dizer o que ele é", "novilha, boi, bezerro…",
                      f"Tião, {quem} é "))
    if a.valor_compra is None:
        acoes.append(("Dizer quanto custou", "o valor que pagou na cabeça",
                      f"Tião, paguei em {quem} "))
    if a.ultima_pesagem is None:
        acoes.append(("Dizer o peso", "nunca foi pesado",
                      f"Tião, {quem} pesou "))

    # E o que ele faz no dia a dia.
    if a.ultima_pesagem is not None:
        acoes.append(("Pesei hoje", "anotar peso novo",
                      f"Tião, pesei {quem} hoje: "))
    acoes.append(("Mudou de pasto", "Sítio Pai e Filho ou Sítio II Ypês",
                  f"Tião, {quem} mudou de pasto pro "))
    if not a.vendido:
        acoes.append(("Vendi", "por quanto e pra quem",
                      f"Tião, vendi {quem} por "))
    acoes.append(("Outra coisa", "falar o que quiser", f"Tião, sobre {quem}: "))
    return acoes


def animal(request, brinco):
    """One animal's card: what it is, what it weighs, what it cost, what it's worth."""
    return _ficha(request, get_object_or_404(_rebanho_base(), brinco=brinco))


def animal_por_id(request, pk):
    """Same card, for an animal with no ear tag to address it by."""
    return _ficha(request, get_object_or_404(_rebanho_base(), pk=pk))


def _ficha(request, bicho):
    Animal.com_cotacoes([bicho])
    despesas = list(bicho.despesas.all())
    return render(request, "gado/animal.html", {
        "a": bicho,
        # Vai pronto no campo do Telegram, faltando só o que ele quer dizer.
        "acoes_tiao": _acoes_tiao(bicho),
        # As pendências vêm primeiro na lista; o template destaca essas.
        "pendentes": sum(1 for f in (not bicho.categoria, bicho.valor_compra is None,
                                     bicho.ultima_pesagem is None) if f),
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

"""Jader's side of the site: read-only, big type, made for a phone.

Deliberately not the admin. However well themed an admin is, it is built for
someone who knows what a changelist is. These are four pages that answer four
questions he actually asks.

Nothing here writes. Everything is one query per page plus prefetches.
"""

from django.db.models import Count, Max, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from . import grafico
from .models import Animal, Categoria, Contraparte, Cotacao, Movimentacao


def _rebanho_base():
    return (Animal.objects
            .select_related("propriedade", "compra", "venda")
            .prefetch_related("pesagens", "despesas"))


def _o_que_da_pra_filtrar():
    """Os valores que as barras de filtro podem oferecer, numa query só.

    Só o que EXISTE no rebanho: o enum tem onze categorias e ele tem duas, e
    oferecer as outras nove daria nove botões que devolvem tela vazia.

    Pasto e categoria saem do MESMO `values_list` de propósito. São duas
    perguntas, mas a lista tem um teste que trava o número de queries da
    página, e duas queries onde uma resolve é o começo de um N+1 por filtro
    novo. O par distinto tem no máximo pastos x categorias linhas.
    """
    pares = set(Animal.objects.values_list("propriedade__nome", "categoria"))
    ordem = [c for c, _ in Categoria.choices]
    return (sorted({p for p, _ in pares if p}),
            # Na ordem do enum, que é a do bicho crescendo -- não em ordem
            # alfabética, que poria "vaca" antes de "bezerro".
            sorted({c for _, c in pares if c},
                   key=lambda c: ordem.index(c) if c in ordem else len(ordem)))


def rebanho(request):
    """The detailed herd list -- the spreadsheet's Animais tab, kept live."""
    propriedade = request.GET.get("propriedade") or ""
    situacao = request.GET.get("situacao") or ""
    categoria = request.GET.get("categoria") or ""

    animais = _rebanho_base()
    if propriedade:
        animais = animais.filter(propriedade__nome=propriedade)
    if categoria:
        animais = animais.filter(categoria=categoria)
    if situacao == "pasto":
        animais = animais.filter(venda__isnull=True)
    elif situacao == "vendido":
        animais = animais.filter(venda__isnull=False)
    animais = Animal.com_cotacoes(animais)

    propriedades, categorias = _o_que_da_pra_filtrar()
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
        "propriedades": propriedades,
        "categorias": categorias,
        "propriedade_ativa": propriedade,
        "situacao_ativa": situacao,
        "categoria_ativa": categoria,
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
    # SEXO antes de categoria, e um OU outro, nunca os dois: é o sexo que
    # escolhe a escada de reposição e o rendimento, e sem ele `mercado` devolve
    # ABATE em silêncio -- bezerro precificado pelo boi gordo, o defeito
    # original. A categoria o `Pesagem.save()` deriva do peso sozinho assim que
    # o sexo é conhecido, que é o mesmo que o Workflow 2 manda o bot perguntar.
    # Pedir as duas daria dois botões com a mesma frase pronta e mandaria ele
    # preencher justamente o campo que a pesagem seguinte sobrescreve.
    if not a.sexo:
        acoes.append(("Dizer se é macho ou fêmea", "é o que decide o preço",
                      f"Tião, {quem} é "))
    elif not a.categoria:
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
        "pendentes": sum(1 for f in (not bicho.sexo, not bicho.categoria,
                                     bicho.valor_compra is None,
                                     bicho.ultima_pesagem is None) if f),
        "pesagens": list(reversed(bicho._pesagens_ordenadas)),
        "despesas": sorted(despesas, key=lambda d: d.data, reverse=True),
        "total_despesas": sum(d.valor for d in despesas) if despesas else None,
        "pagina": "rebanho",
    })


def _escada_de_hoje():
    """As oito linhas de reposição da tela: o último pregão de cada degrau.

    Degrau por degrau, e não "tudo do último pregão": uma coleta interrompida
    no meio deixaria a escada faltando justamente os degraus que não deram
    tempo, e a tela mostraria três linhas onde há quatro. São oito queries,
    mas oito fixas -- não crescem com nada.
    """
    escadas = {}
    for sexo, rotulo in (("macho", "machos"), ("femea", "fêmeas")):
        praca = Cotacao.PRACA_REPOSICAO[sexo]
        cats = Cotacao.ESCADA_FEMEA if sexo == "femea" else Cotacao.ESCADA_MACHO
        linhas = [Cotacao.objects.filter(mercado=Cotacao.REPOSICAO, categoria=c,
                                         praca=praca).order_by("-data_pregao").first()
                  for c in cats]
        linhas = [c for c in linhas if c]
        if linhas:
            escadas[rotulo] = linhas
    return escadas


def _mesma_base(hoje, antes):
    """O pregão anterior avalia o rebanho pelo MESMO caminho que o de hoje?

    Esta é a guarda que decide se a comparação pode aparecer. Sem escada de
    reposição na data anterior, `Animal.mercado` devolve abate -- ela exige
    dois pontos publicados -- e todo bezerro passa a ser precificado pela
    arroba do boi gordo. A diferença entre os dois dias viraria a diferença
    entre dois MÉTODOS, não entre dois preços, e chegaria na tela com cara de
    notícia de mercado. É exatamente o caso de hoje: o abate tem quinze
    pregões guardados e a reposição tem um. Melhor não mostrar nada.
    """
    cot_hoje, esc_hoje = hoje
    cot_antes, esc_antes = antes
    if any(cot_hoje[c] and not cot_antes[c] for c in cot_hoje):
        return False
    return all(len(esc_antes[s]) >= 2 for s in esc_hoje if len(esc_hoje[s]) >= 2)


def _boiada_no_pasto():
    """As cabeças que ainda são dele. Enxuta: aqui só interessa o peso.

    `_rebanho_base` traz pasto, compra, venda e despesas -- nada disso entra
    na conta do valor, e prefetch que ninguém lê é query paga à toa.
    """
    return list(Animal.objects.filter(venda__isnull=True)
                .prefetch_related("pesagens"))


def _quanto_vale(animais):
    valores = [a.valor_atual for a in animais if a.valor_atual is not None]
    return sum(valores) if valores else None


def cotacao(request):
    """Os dois mercados, e o que eles significam para a boiada dele.

    A ordem da página é a da pergunta que ele faz: primeiro quanto a boiada
    vale hoje, depois todos os preços do dia juntos, depois como o preço
    andou, e só no fim o histórico linha a linha. Antes era o contrário --
    três tabelas de quinze pregões entre a cotação de abate e a de reposição,
    que num celular são três telas de rolagem até chegar no preço do bezerro.
    """
    datas = list(Cotacao.objects.values_list("data_pregao", flat=True)
                 .distinct().order_by("-data_pregao")[:2])
    pregao_hoje = datas[0] if datas else None
    pregao_antes = datas[1] if len(datas) > 1 else None

    # Quinze pregões de abate, numa consulta só, e reaproveitados três vezes:
    # as caixas do dia, o gráfico e a tabela de histórico saem todos daqui.
    datas_abate = list(Cotacao.objects.filter(mercado=Cotacao.ABATE)
                       .values_list("data_pregao", flat=True)
                       .distinct().order_by("-data_pregao")[:15])
    historico = list(Cotacao.objects.filter(mercado=Cotacao.ABATE,
                                            data_pregao__in=datas_abate)
                     .order_by("-data_pregao", "categoria"))

    abate, serie = [], []
    for i, (chave, rotulo) in enumerate(Cotacao.CATEGORIAS_ABATE):
        linhas = [c for c in historico if c.categoria == chave]
        if not linhas:
            continue
        abate.append((rotulo, linhas[0]))
        pontos = [(c.data_pregao, c.bruto_a_vista) for c in linhas
                  if c.bruto_a_vista is not None]
        if pontos:
            serie.append({"nome": rotulo, "cor": grafico.CORES[i], "pontos": pontos})

    # Os dois passes usam AS MESMAS cabeças, e quem roda por último é quem
    # fica anexado nelas -- por isso o pregão anterior vem primeiro e o de
    # hoje depois, deixando a página com a base certa na mão.
    boiada = _boiada_no_pasto()
    base_hoje = Animal.base_de_cotacoes()
    antes = None
    if pregao_antes is not None:
        base_antes = Animal.base_de_cotacoes(pregao_antes)
        if _mesma_base(base_hoje, base_antes):
            Animal.com_cotacoes(boiada, base=base_antes)
            antes = _quanto_vale(boiada)
    Animal.com_cotacoes(boiada, base=base_hoje)
    valor_boiada = _quanto_vale(boiada)
    variacao = (None if antes is None or valor_boiada is None
                else valor_boiada - antes)

    return render(request, "gado/cotacao.html", {
        "abate": abate,
        "escadas": _escada_de_hoje(),
        "historico": historico,
        "grafico": grafico.linha(serie, "Como a arroba andou nos últimos pregões"),
        "pregoes_no_grafico": len(datas_abate),
        "valor_boiada": valor_boiada,
        "cabecas_boiada": len(boiada),
        "variacao": variacao,
        "pregao_hoje": pregao_hoje,
        "pregao_antes": pregao_antes if variacao is not None else None,
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

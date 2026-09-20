"""Domain models for the Batistela cattle operation.

Every table here already existed before Django did -- the bot has been writing
to them for weeks. Migration 0001 therefore mirrors the live schema exactly and
is applied with --fake-initial: Django adopts the tables instead of creating
them. Anything new arrives in later migrations, so the history stays honest.

From here on, schema changes are born as Django migrations. No more hand-applied
psql DDL -- that is how `cotacoes` ended up with no history at all.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from . import precificacao

# Carcass yield, the numbers Seu Jader uses. The arroba the market pays is of
# CARCASS, not live weight: dividing live weight by 15 nearly doubles an
# animal's value. Same constants as the tiao-cotacao skill.
RENDIMENTO_MACHO = 55.0
RENDIMENTO_FEMEA = 45.0
KG_POR_ARROBA = 15.0

class Sexo(models.TextChoices):
    MACHO = "macho", "macho"
    FEMEA = "femea", "fêmea"


class Categoria(models.TextChoices):
    DESMAMA = "desmama", "desmama"
    BEZERRO = "bezerro", "bezerro"
    GARROTE = "garrote", "garrote"
    NOVILHO = "novilho", "novilho"
    BOI_MAGRO = "boi magro", "boi magro"
    BOI = "boi", "boi"
    TOURO = "touro", "touro"
    BEZERRA = "bezerra", "bezerra"
    NOVILHA = "novilha", "novilha"
    VACA_MAGRA = "vaca magra", "vaca magra"
    VACA = "vaca", "vaca"


# The category settles the sex -- a vaca is never macho. Kept in ONE place so
# the derivation and the coherence check cannot drift apart. This matters in
# money: sex picks the carcass yield (55% vs 45%), so an animal recorded as a
# vaca but flagged macho would be priced about R$ 1.100 too high, quietly.
#
# `desmama` is deliberately OUT of this map: it serves both sexes -- a macho
# weans at 180 kg, a fêmea at 165 kg -- so no category alone tells you which.
# It lives in CATEGORIAS_AMBIGUAS below, where the sex is required instead of
# derived.
SEXO_DA_CATEGORIA = {
    Categoria.BEZERRO: Sexo.MACHO,
    Categoria.GARROTE: Sexo.MACHO,
    Categoria.NOVILHO: Sexo.MACHO,
    Categoria.BOI_MAGRO: Sexo.MACHO,
    Categoria.BOI: Sexo.MACHO,
    Categoria.TOURO: Sexo.MACHO,
    Categoria.BEZERRA: Sexo.FEMEA,
    Categoria.NOVILHA: Sexo.FEMEA,
    Categoria.VACA_MAGRA: Sexo.FEMEA,
    Categoria.VACA: Sexo.FEMEA,
}

# Categorias que existem nas duas escadas de preço: o sexo não é dedutível
# delas, e por isso passa a ser exigido em vez de preenchido.
CATEGORIAS_AMBIGUAS = {Categoria.DESMAMA}


def _sem_acento(s):
    s = str(s or "").strip().lower()
    for de, para in zip("áàâãéêíóôõúç", "aaaaeeiooouc"):
        s = s.replace(de, para)
    return s


# The bot writes through the ORM in free prose -- "fêmea", "FEMEA", "f", "vaca
# gorda". Storage is strict; the boundary is forgiving. Normalising here means
# the CHECK constraint never has to reject something a human clearly meant.
_APELIDOS_SEXO = {"f": Sexo.FEMEA, "femea": Sexo.FEMEA, "fema": Sexo.FEMEA,
                  "m": Sexo.MACHO, "macho": Sexo.MACHO}
_APELIDOS_CATEGORIA = {"vaca gorda": Categoria.VACA, "boi gordo": Categoria.BOI}


def normalizar_sexo(valor):
    """Free text -> a Sexo value, or None when it is not recognisable."""
    if not valor:
        return None
    chave = _sem_acento(valor)
    if chave in Sexo.values:
        return chave
    return _APELIDOS_SEXO.get(chave)


def normalizar_categoria(valor):
    """Free text -> a Categoria value, or None when it is not recognisable."""
    if not valor:
        return None
    chave = _sem_acento(valor)
    if chave in Categoria.values:
        return chave
    return _APELIDOS_CATEGORIA.get(chave)


def e_femea(categoria_ou_sexo):
    valor = normalizar_sexo(categoria_ou_sexo)
    if valor is None:
        cat = normalizar_categoria(categoria_ou_sexo)
        valor = SEXO_DA_CATEGORIA.get(cat) if cat else None
    return valor == Sexo.FEMEA


class Propriedade(models.Model):
    """Where the animal is: Dois Ipes, Pai e Filho, Arrendamento 1 and 2.

    A table rather than a choices field so Jader's son can add a new pasture in
    the admin without waiting for a deploy.
    """

    nome = models.TextField("nome", unique=True)
    observacoes = models.TextField("observações", blank=True, null=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        db_table = "propriedades"
        verbose_name = "propriedade"
        verbose_name_plural = "propriedades"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Contraparte(models.Model):
    """Whoever is on the other side of a deal -- supplier or buyer.

    One table, two roles, told apart by `tipo`. The admin splits it into
    Fornecedores and Compradores through proxy models.
    """

    VENDEDOR = "vendedor"
    COMPRADOR = "comprador"

    nome = models.TextField("nome")
    tipo = models.TextField("tipo")
    telefone = models.TextField("telefone", blank=True, null=True)
    cidade = models.TextField("cidade", blank=True, null=True)
    observacoes = models.TextField("observações", blank=True, null=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        db_table = "compradores"
        verbose_name = "contraparte"
        verbose_name_plural = "contrapartes"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Movimentacao(models.Model):
    """A purchase or a sale. Same shape, told apart by `tipo`."""

    COMPRA = "compra"
    VENDA = "venda"

    tipo = models.TextField("tipo")
    data = models.DateField("data")
    valor = models.DecimalField("valor", max_digits=12, decimal_places=2,
                                blank=True, null=True)
    comprador = models.ForeignKey(
        Contraparte, models.DO_NOTHING, blank=True, null=True,
        verbose_name="contraparte", related_name="movimentacoes")
    quantidade = models.IntegerField("quantidade", blank=True, null=True)
    # A deal is priced in one of the ways below, and which one depends on who
    # is on the other side. A frigorífico buys ready cattle by the arroba;
    # someone buying calves for reposição buys by the quilo vivo; a neighbour
    # buys the lot for a round number. Whichever he knows goes in; the rest is
    # derived.
    preco_arroba = models.DecimalField(
        "preço da arroba", max_digits=10, decimal_places=2, blank=True, null=True,
        help_text="Quando o negócio foi fechado por arroba")
    preco_kg = models.DecimalField(
        "preço do quilo", max_digits=10, decimal_places=2, blank=True, null=True,
        help_text="Quando o negócio foi fechado por quilo vivo (reposição)")
    observacoes = models.TextField("observações", blank=True, null=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        db_table = "compras"
        verbose_name = "movimentação"
        verbose_name_plural = "movimentações"
        ordering = ["-data"]

    def __str__(self):
        quem = self.comprador.nome if self.comprador else "sem contraparte"
        return f"{self.tipo} de {self.quantidade or '?'} — {quem} — {self.data:%d/%m/%Y}"

    @property
    def valor_por_cabeca(self):
        """The flat split -- total divided by head count.

        The crudest of the three ways to price a head, and the only one that is
        wrong per animal: it gives the 563 kg cow and the 343 kg cow the same
        money. Used only when nothing better was recorded.
        """
        if not self.valor or not self.quantidade:
            return None
        return self.valor / self.quantidade

    @property
    def animais(self):
        """The heads on this deal, whichever side it is."""
        return (self.animais_vendidos if self.tipo == self.VENDA
                else self.animais_comprados)

    @property
    def total_apurado(self):
        """What the individual heads add up to.

        May differ from `valor`: he might record the deal total AND a per-head
        price, or an arroba price whose sum lands a few reais off the round
        number that was actually paid. Both are worth keeping -- the difference
        is information, not an error to hide.
        """
        vals = [a.valor_venda_apurado if self.tipo == self.VENDA else a.valor_compra
                for a in self.animais.all()]
        vals = [v for v in vals if v is not None]
        return sum(vals) if vals else None

    @property
    def diferenca_do_total(self):
        """Recorded total minus what the heads add up to. None when either is missing."""
        apurado = self.total_apurado
        if self.valor is None or apurado is None:
            return None
        return self.valor - apurado


class Animal(models.Model):
    """A head of cattle -- identified by ear tag when there is one.

    Much of what Jader will type in at the start is history: animals he bought
    and never weighed, animals already sold, animals he only ever called "a
    vaca do chifre quebrado". A record that refuses to exist until every field
    is known would simply lose that history, so almost everything here is
    optional. The one floor is that an animal must be REFERABLE: a tag, or a
    phrase he recognises. An animal with neither can never be spoken about
    again, which makes it worse than not recorded.
    """

    # Nullable AND unique: Postgres treats NULLs as distinct, so any number of
    # untagged animals coexist while real tags stay unique.
    brinco = models.TextField("brinco", unique=True, blank=True, null=True)
    referencia = models.TextField(
        "referência", blank=True, null=True,
        help_text="Como o patrão chama o bicho quando não tem brinco")
    raca = models.TextField("raça", blank=True, null=True)
    categoria = models.CharField("categoria", max_length=16, blank=True, null=True,
                                 choices=Categoria)
    sexo = models.CharField("sexo", max_length=16, blank=True, null=True,
                            choices=Sexo)
    data_nascimento = models.DateField("data de nascimento", blank=True, null=True)
    compra = models.ForeignKey(
        Movimentacao, models.DO_NOTHING, blank=True, null=True,
        verbose_name="compra", related_name="animais_comprados")
    observacoes = models.TextField("observações", blank=True, null=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    valor_compra = models.DecimalField("valor de compra", max_digits=12,
                                       decimal_places=2, blank=True, null=True)
    pelagem = models.TextField("pelagem", blank=True, null=True)
    propriedade = models.ForeignKey(
        Propriedade, models.SET_NULL, blank=True, null=True,
        verbose_name="propriedade", related_name="animais")
    venda = models.ForeignKey(
        "Movimentacao", models.SET_NULL, blank=True, null=True,
        verbose_name="venda", related_name="animais_vendidos")
    # What THIS head fetched, when he knows it per head. Left empty when the
    # deal was closed by the arroba or as a single lot price -- then it is
    # derived. Storing it never overwrites what he typed.
    valor_venda = models.DecimalField(
        "valor de venda", max_digits=12, decimal_places=2, blank=True, null=True,
        help_text="Quanto esta cabeça saiu, quando ele sabe o valor por cabeça")
    peso_venda = models.DecimalField(
        "peso na venda", max_digits=8, decimal_places=2, blank=True, null=True,
        help_text="Peso no dia da venda, se diferente da última pesagem")
    # The arroba is not one price per deal. Within a single sale different heads
    # can go at different prices -- the buyer decides, animal by animal, and the
    # reasons are his. So the price belongs to the HEAD, with the deal's price as
    # the fallback for the rest. Nothing here infers a price from weight or from
    # any other field: it is recorded, never derived.
    preco_arroba_venda = models.DecimalField(
        "preço da arroba desta cabeça", max_digits=10, decimal_places=2,
        blank=True, null=True,
        help_text="Quando esta cabeça saiu por arroba diferente da do negócio")
    preco_kg_venda = models.DecimalField(
        "preço do quilo desta cabeça", max_digits=10, decimal_places=2,
        blank=True, null=True,
        help_text="Quando esta cabeça saiu por quilo diferente do negócio")
    # O que ele digitou sobre a venda -- nunca recalculado depois. A Tarefa 10
    # vai propor correção automática de categoria pelo peso; esse campo fica
    # de fora disso, porque descreve o que de fato aconteceu, não uma
    # estimativa.
    categoria_venda = models.CharField(
        "categoria na venda", max_length=16, choices=Categoria, blank=True, null=True,
        help_text="Como o bicho saiu — fato histórico, nunca recalculado")

    class Meta:
        db_table = "animais"
        verbose_name = "animal"
        verbose_name_plural = "animais"
        ordering = ["brinco"]
        # Enforced by the database, not only by the form. The bot writes through
        # the ORM and `save()` does not run `full_clean()`, so a choices field
        # alone would let a typo through. These are the last line.
        constraints = [
            # Referable or not recorded. Everything else may be filled in later.
            models.CheckConstraint(
                condition=models.Q(brinco__isnull=False) | models.Q(referencia__isnull=False),
                name="animais_identificavel"),
            models.CheckConstraint(
                condition=models.Q(sexo__in=Sexo.values) | models.Q(sexo__isnull=True),
                name="animais_sexo_valido"),
            models.CheckConstraint(
                condition=models.Q(categoria__in=Categoria.values)
                | models.Q(categoria__isnull=True),
                name="animais_categoria_valida"),
            models.CheckConstraint(
                condition=models.Q(categoria_venda__in=Categoria.values)
                | models.Q(categoria_venda__isnull=True),
                name="animais_categoria_venda_valida"),
        ]

    def __str__(self):
        return f"brinco {self.brinco}" if self.brinco else self.identificacao

    @property
    def identificacao(self):
        """What to call this animal on screen and out loud."""
        if self.brinco:
            return self.brinco
        if self.referencia:
            return self.referencia
        return f"sem brinco #{self.pk}"

    @property
    def como_falar(self):
        """How to name this animal inside a sentence."""
        return f"o brinco {self.brinco}" if self.brinco else self.identificacao

    @property
    def faltando(self):
        """Which useful facts this record still lacks.

        Backfilled history arrives full of holes, and holes are fine -- but they
        must be VISIBLE, or they never get filled. Each entry names what the gap
        actually costs.
        """
        faltas = []
        if not self.brinco:
            faltas.append("brinco")
        if not self.categoria:
            faltas.append("categoria (sem ela não dá pra saber o valor)")
        if self.ultima_pesagem is None:
            faltas.append("nunca foi pesado")
        if not self.propriedade_id and not self.venda_id:
            faltas.append("em qual pasto está")
        if self.valor_compra is None:
            faltas.append("quanto custou")
        return faltas

    def clean_fields(self, exclude=None):
        # Must happen HERE, not in clean(): Django validates choices inside
        # clean_fields, which runs first, so "fêmea" would be rejected before
        # clean() ever got the chance to turn it into "femea".
        if self.categoria:
            self.categoria = normalizar_categoria(self.categoria) or self.categoria
        if self.sexo:
            self.sexo = normalizar_sexo(self.sexo) or self.sexo
        super().clean_fields(exclude=exclude)

    def clean(self):
        """Preenche o sexo a partir da categoria, e recusa contradição.

        Exceção: as categorias ambíguas (hoje só `desmama`) servem aos dois
        sexos. Nelas o sexo é EXIGIDO, porque é ele que escolhe a escada de
        preço -- e uma desmama sem sexo não tem preço.
        """
        super().clean()
        if self.categoria in CATEGORIAS_AMBIGUAS and not self.sexo:
            raise ValidationError({"sexo": (
                f"{self.get_categoria_display()} pode ser macho ou fêmea; "
                "diga qual, que é o sexo que decide o preço")})
        esperado = SEXO_DA_CATEGORIA.get(self.categoria) if self.categoria else None
        if not esperado:
            return
        if not self.sexo:
            self.sexo = esperado          # a categoria já diz; não faça perguntar
        elif self.sexo != esperado:
            raise ValidationError({"sexo": (
                f"{self.get_categoria_display()} é {Sexo(esperado).label}, "
                f"não {Sexo(self.sexo).label}")})

    def save(self, *args, **kwargs):
        # `save()` never calls clean() on its own, and the bot saves through the
        # ORM -- without this a row could be stored with a blank or contradictory
        # sex. Only the two enum fields are validated, and uniqueness and
        # constraints are left to the database, so this costs no extra query.
        self.full_clean(
            exclude=[f.name for f in self._meta.fields
                     if f.name not in ("categoria", "sexo")],
            validate_unique=False, validate_constraints=False)
        return super().save(*args, **kwargs)

    @property
    def rendimento(self):
        """Carcass yield for this animal, by sex. Falls back to category."""
        return RENDIMENTO_FEMEA if e_femea(self.sexo or self.categoria) else RENDIMENTO_MACHO

    # The columns below are the ones Jader's spreadsheet computed by formula.
    # They are derived, never stored -- a stored total goes stale the moment a
    # weighing or an expense is added. On the herd list the view annotates them
    # in one query; these properties serve the single-animal page.

    # These sort in Python on purpose. `self.pesagens.order_by(...)` issues a
    # fresh query even when pesagens was prefetched -- order_by discards the
    # prefetch cache -- which is one query per animal on a 300-head list.
    # Sorting the cached list keeps the whole page at one query.

    @property
    def _pesagens_ordenadas(self):
        return sorted(self.pesagens.all(), key=lambda p: p.data)

    @property
    def primeira_pesagem(self):
        ps = self._pesagens_ordenadas
        return ps[0] if ps else None

    @property
    def ultima_pesagem(self):
        ps = self._pesagens_ordenadas
        return ps[-1] if ps else None

    @property
    def peso_atual_kg(self):
        p = self.ultima_pesagem
        return float(p.peso_kg) if p else None

    @property
    def peso_arrobas(self):
        """Carcass arrobas -- what the market actually pays for."""
        kg = self.peso_atual_kg
        if kg is None:
            return None
        return kg * (self.rendimento / 100.0) / KG_POR_ARROBA

    @property
    def total_despesas(self):
        return sum((d.valor for d in self.despesas.all()), start=Decimal("0"))

    @property
    def cotacao_atual(self):
        # When a view has already fetched the quotes for the whole page it
        # attaches them here; otherwise ask for this animal's own.
        cat = Cotacao.categoria_de(self.categoria or self.sexo)
        if hasattr(self, "_cotacoes"):
            return self._cotacoes.get(cat)
        return Cotacao.mais_recente(cat)

    def _escada_reposicao(self):
        # Mesmo padrão de `cotacao_atual`: usa o que `com_cotacoes` já
        # carregou para a lista inteira, e só consulta o banco sozinho quando
        # ninguém carregou por ela -- a página de um único animal.
        if hasattr(self, "_escadas"):
            return self._escadas["femea" if e_femea(self.sexo) else "macho"]
        return Cotacao.escada_reposicao(self.sexo)

    @staticmethod
    def com_cotacoes(animais):
        """Hands one quote lookup to a whole list of animals.

        Use it whenever you iterate more than one animal: the alternative is a
        query per head.
        """
        cotacoes = Cotacao.ultimas_por_categoria()
        escadas = {"macho": Cotacao.escada_reposicao("macho"),
                  "femea": Cotacao.escada_reposicao("femea")}
        animais = list(animais)
        for a in animais:
            a._cotacoes = cotacoes
            a._escadas = escadas
        return animais

    @property
    def mercado(self):
        """Em que mercado este bicho é vendido HOJE, pelo peso dele.

        A troca acontece no cruzamento das duas curvas, não num peso fixo.
        Fêmea segue no abate por decisão do dono: as matrizes dele pesam de
        343 a 563 kg, todas acima do cruzamento feminino de qualquer forma.
        """
        # `self.sexo`, NUNCA `self.sexo or self.categoria`: `desmama` serve aos
        # dois sexos e ficou fora de SEXO_DA_CATEGORIA, então e_femea() de uma
        # categoria ambígua devolve False -- isto é, MACHO -- em silêncio. Uma
        # cria fêmea iria para a escada masculina, R$ 15,50/kg em vez de
        # R$ 13,20/kg. Sem sexo não há escada: devolve ABATE, que não estima.
        kg = self.peso_atual_kg
        if kg is None or not self.sexo or e_femea(self.sexo):
            return Cotacao.ABATE
        pontos = self._escada_reposicao()
        # `cotacao_atual`, não `Cotacao.mais_recente_abate` direto: sexo já
        # está garantido macho aqui, e `categoria_de` de qualquer categoria
        # masculina cai em BOI -- exatamente a cotação que `cotacao_atual` já
        # busca, e via `self._cotacoes` quando `com_cotacoes` carregou a
        # lista. Chamar o classmethod aqui reabriria o N+1: uma query de
        # abate por animal, o mesmo defeito que a escada já evitava.
        abate = self.cotacao_atual
        # len < 2, não "vazio": escada() levanta com menos de dois pontos, e
        # uma coleta interrompida pela metade devolve um ponto só.
        if len(pontos) < 2 or not abate or abate.bruto_a_vista is None:
            return Cotacao.ABATE
        limite = precificacao.cruzamento(pontos, self.rendimento,
                                         float(abate.bruto_a_vista))
        return Cotacao.ABATE if kg >= limite else Cotacao.REPOSICAO

    @property
    def unidade(self):
        return Cotacao.KG if self.mercado == Cotacao.REPOSICAO else Cotacao.ARROBA

    @property
    def pago_por_kg(self):
        """Quanto ele pagou por quilo vivo, pelo peso de ENTRADA do animal."""
        p = self.primeira_pesagem
        if not self.valor_compra or p is None or not p.peso_kg:
            return None
        return self.valor_compra / Decimal(str(p.peso_kg))

    @property
    def cotacao_por_kg(self):
        """O R$/kg que a curva paga no peso de hoje."""
        kg = self.peso_atual_kg
        if kg is None or self.mercado != Cotacao.REPOSICAO:
            return None
        v = precificacao.valor_reposicao(kg, self._escada_reposicao())
        return Decimal(str(round(v / kg, 2))) if v is not None else None

    @property
    def ganho_por_kg(self):
        pago, vale = self.pago_por_kg, self.cotacao_por_kg
        return None if pago is None or vale is None else vale - pago

    # --- O que ele calcula de cabeça toda vez que pesa -----------------------
    # "Paguei quanto na arroba?" é a pergunta da engorda: você compra a X a
    # arroba e vende a Y, e ganha nos dois lados -- no preço e no peso que o
    # bicho pôs. Sem isso ele faz a divisão no papel toda vez.

    @property
    def arrobas_na_compra(self):
        """Arrobas pela PRIMEIRA pesagem -- o peso de entrada do animal.

        Usar o peso de hoje diluiria o preço pago pelo que o bicho engordou
        depois, e faria parecer que ele comprou mais barato do que comprou.
        """
        p = self.primeira_pesagem
        if p is None:
            return None
        return float(p.peso_kg) * (self.rendimento / 100.0) / KG_POR_ARROBA

    @property
    def pago_por_arroba(self):
        arrobas = self.arrobas_na_compra
        if not self.valor_compra or not arrobas:
            return None
        return self.valor_compra / Decimal(str(arrobas))

    @property
    def cotacao_por_arroba(self):
        """Today's quote per arroba.

        Only SP Araçatuba is collected, and it is quoted per arroba. The two RS
        praças that quote per kilo are refused by the scraper, so nothing here
        ever has to convert units.
        """
        c = self.cotacao_atual
        return c.bruto_a_vista if c else None

    @property
    def ganho_por_arroba(self):
        pago, vale = self.pago_por_arroba, self.cotacao_por_arroba
        if pago is None or vale is None:
            return None
        return vale - pago

    @property
    def custo_total(self):
        """Purchase plus everything spent on the animal since."""
        if self.valor_compra is None:
            return None
        return self.valor_compra + self.total_despesas

    @property
    def ganho(self):
        """What the animal is worth today minus what it has cost.

        Only meaningful while he still owns it. Once sold, what matters is what
        he actually got -- see `resultado`.
        """
        vale, custo = self.valor_atual, self.custo_total
        if vale is None or custo is None:
            return None
        return vale - custo

    @property
    def vendido(self):
        return self.venda_id is not None

    @property
    def peso_na_venda(self):
        """Weight the sale was priced on: the recorded one, else the last weighing."""
        if self.peso_venda is not None:
            return float(self.peso_venda)
        return self.peso_atual_kg

    @property
    def arrobas_na_venda(self):
        kg = self.peso_na_venda
        if kg is None:
            return None
        return kg * (self.rendimento / 100.0) / KG_POR_ARROBA

    def _venda_por_preco_unitario(self):
        """Níveis 2 e 3 de `valor_venda_apurado`: um preço por quilo ou por
        arroba, da cabeça ou do negócio.

        Devolve `(valor, rótulo)`, ou `(None, None)` quando nenhum dos dois
        níveis tem preço. Uma única conta serve `valor_venda_apurado` e
        `origem_valor_venda` de propósito -- as duas jamais podem discordar
        sobre de onde o número veio.
        """
        peso = self.peso_na_venda
        arrobas = self.arrobas_na_venda
        # Nível 2 -- o que ele disse sobre ESTA cabeça.
        if self.preco_kg_venda is not None and peso is not None:
            valor = Decimal(str(peso)) * self.preco_kg_venda
            rotulo = f"{peso:.0f} kg × R$ {self.preco_kg_venda} (quilo desta cabeça)"
            return valor, rotulo.replace(".", ",")
        if self.preco_arroba_venda is not None and arrobas is not None:
            valor = Decimal(str(round(arrobas, 4))) * self.preco_arroba_venda
            rotulo = f"{arrobas:.2f} @ × R$ {self.preco_arroba_venda} (arroba desta cabeça)"
            return valor, rotulo.replace(".", ",")
        # Nível 3 -- o que ele disse sobre o NEGÓCIO inteiro.
        if self.venda.preco_kg is not None and peso is not None:
            valor = Decimal(str(peso)) * self.venda.preco_kg
            rotulo = f"{peso:.0f} kg × R$ {self.venda.preco_kg} o quilo"
            return valor, rotulo.replace(".", ",")
        if self.venda.preco_arroba is not None and arrobas is not None:
            valor = Decimal(str(round(arrobas, 4))) * self.venda.preco_arroba
            rotulo = f"{arrobas:.2f} @ × R$ {self.venda.preco_arroba}"
            return valor, rotulo.replace(".", ",")
        return None, None

    @property
    def valor_venda_apurado(self):
        """What this head fetched, from whichever fact he actually has.

        He prices a sale at one of four levels of specificity, from what he
        said about THIS head to what he said about the whole lot:

          1. per head, an absolute value -- "essa saiu por 5.200"
          2. per head, a unit price -- kg vivo or arroba, decided one by one
          3. per deal, a unit price -- one R$/kg or R$/@ for everything
          4. per deal, one number for the lot -- selling to a neighbour

        They are tried in that order, most specific first, regardless of
        unit: a head priced by arroba still beats a deal priced by the kilo.
        What he typed always wins over anything derived, so editing a single
        head later does not get silently recomputed away.
        """
        if not self.vendido:
            return None
        if self.valor_venda is not None:
            return self.valor_venda
        valor, _ = self._venda_por_preco_unitario()
        if valor is not None:
            return valor
        return self.venda.valor_por_cabeca

    @property
    def origem_valor_venda(self):
        """Where the sale value came from -- shown so a derived number is never
        mistaken for a recorded one."""
        if not self.vendido:
            return None
        if self.valor_venda is not None:
            return "valor por cabeça"
        _, rotulo = self._venda_por_preco_unitario()
        if rotulo is not None:
            return rotulo
        if self.venda.valor_por_cabeca is not None:
            return "rateio do total da venda"
        return None

    @property
    def resultado(self):
        """Realised profit on a sold animal: what it fetched, minus what it cost.

        This is the number that is TRUE about a sold animal. `valor_atual` for
        one he no longer owns is a hypothetical -- what it would be worth if he
        had kept it -- and showing that as its value overstates the herd.
        """
        venda, custo = self.valor_venda_apurado, self.custo_total
        if venda is None or custo is None:
            return None
        return venda - custo

    @property
    def valor_atual(self):
        """ESTIMATIVA do que esta cabeça renderia, na cotação de referência.

        Não é promessa, e as telas não podem soar como uma. No abate a
        cotação é a média publicada de SP Araçatuba; o que ele recebe de
        fato é o que o comprador oferece, e varia por comprador e por
        animal -- duas cabeças do mesmo lote podem sair por arrobas
        diferentes. Na reposição vem da curva interpolada, não do R$/kg da
        faixa. Serve para decidir se vende, nunca para o que ele vai
        receber.

        Um animal vendido tem um número real em vez deste: `valor_venda_apurado`.
        """
        kg = self.peso_atual_kg
        if kg is None:
            return None
        if self.mercado == Cotacao.REPOSICAO:
            v = precificacao.valor_reposicao(kg, self._escada_reposicao())
            return Decimal(str(round(v, 2))) if v is not None else None
        cot = self.cotacao_atual
        if cot is None or cot.bruto_a_vista is None:
            return None
        return Decimal(str(round(
            precificacao.valor_abate(kg, self.rendimento, float(cot.bruto_a_vista)), 2)))


class Pesagem(models.Model):
    # CASCADE, not the DO_NOTHING inspectdb produced: deleting an animal in the
    # admin with DO_NOTHING leaves orphan weighings and trips the foreign key.
    animal = models.ForeignKey(Animal, models.CASCADE,
                               verbose_name="animal", related_name="pesagens")
    data = models.DateField("data")
    peso_kg = models.DecimalField("peso (kg)", max_digits=8, decimal_places=2)
    observacoes = models.TextField("observações", blank=True, null=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        db_table = "pesagens"
        verbose_name = "pesagem"
        verbose_name_plural = "pesagens"
        ordering = ["-data"]
        # A re-sent photo must update the row, not duplicate it: a duplicated
        # weighing corrupts the history that catches a misread ear tag.
        unique_together = (("animal", "data"),)

    def __str__(self):
        return f"{self.animal.brinco} — {self.peso_kg} kg em {self.data:%d/%m/%Y}"


class Despesa(models.Model):
    """Money spent on one animal. Types come from Jader's own spreadsheet."""

    VETERINARIA = "VETERINARIA"
    ALIMENTACAO = "ALIMENTACAO"
    TRANSPORTE = "TRANSPORTE"
    MEDICACAO = "MEDICACAO"
    OUTRO = "OUTRO"
    TIPOS = [
        (VETERINARIA, "veterinária"),
        (ALIMENTACAO, "alimentação"),
        (TRANSPORTE, "transporte"),
        (MEDICACAO, "medicação"),
        (OUTRO, "outro"),
    ]

    animal = models.ForeignKey(Animal, models.CASCADE,
                               verbose_name="animal", related_name="despesas")
    valor = models.DecimalField("valor", max_digits=12, decimal_places=2)
    data = models.DateField("data")
    tipo = models.CharField("tipo", max_length=16, choices=TIPOS)
    detalhes = models.TextField("detalhes", blank=True, null=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        db_table = "despesas"
        verbose_name = "despesa"
        verbose_name_plural = "despesas"
        ordering = ["-data"]

    def __str__(self):
        return f"{self.get_tipo_display()} — R$ {self.valor} em {self.data:%d/%m/%Y}"


class Cotacao(models.Model):
    """Daily market price, written by the 19:00 cron in the tiao-cotacao skill.

    Only the BRUTO prices are collected. Funrural, Senar and variação exist on
    the site and are deliberately not read -- a column you don't read can't
    misalign you, and the three category pages don't share a column count.
    """

    ABATE = "abate"
    REPOSICAO = "reposicao"
    MERCADOS = [(ABATE, "abate"), (REPOSICAO, "reposição")]

    ARROBA = "arroba"
    KG = "kg"
    UNIDADES = [(ARROBA, "R$ por arroba de carcaça"), (KG, "R$ por quilo vivo")]

    BOI = "boi"
    NOVILHA = "novilha"
    VACA = "vaca"
    DESMAMA = "desmama"
    BEZERRO = "bezerro"
    GARROTE = "garrote"
    BOI_MAGRO = "boi magro"
    BEZERRA = "bezerra"
    VACA_MAGRA = "vaca magra"

    # Lista COMPLETA, nunca delta: ao redigir a spec a versao em delta perdeu
    # 'bezerro', que e' exatamente a categoria que motivou este trabalho.
    CATEGORIAS = [
        (BOI, "boi gordo"), (NOVILHA, "novilha"), (VACA, "vaca gorda"),
        (DESMAMA, "desmama"), (BEZERRO, "bezerro"), (GARROTE, "garrote"),
        (BOI_MAGRO, "boi magro"), (BEZERRA, "bezerra"), (VACA_MAGRA, "vaca magra"),
    ]

    CATEGORIAS_ABATE = [(BOI, "boi gordo"), (NOVILHA, "novilha"), (VACA, "vaca gorda")]

    mercado = models.CharField("mercado", max_length=16, choices=MERCADOS, default=ABATE)
    unidade = models.CharField("unidade", max_length=8, choices=UNIDADES, default=ARROBA)
    categoria = models.CharField("categoria", max_length=16, choices=CATEGORIAS)
    praca = models.TextField("praça")
    data_pregao = models.DateField("data do pregão")
    bruto_a_vista = models.DecimalField("bruto à vista", max_digits=10,
                                        decimal_places=2, blank=True, null=True)
    bruto_30d = models.DecimalField("bruto 30 dias", max_digits=10,
                                    decimal_places=2, blank=True, null=True)
    rs_kg = models.DecimalField("R$ por quilo vivo", max_digits=10,
                                decimal_places=2, blank=True, null=True)
    rs_cabeca = models.DecimalField("R$ por cabeça", max_digits=12,
                                    decimal_places=2, blank=True, null=True)
    peso_ref_kg = models.DecimalField("peso de referência", max_digits=8,
                                      decimal_places=2, blank=True, null=True)
    coletado_em = models.DateTimeField("coletado em", auto_now_add=True)

    class Meta:
        db_table = "cotacoes"
        verbose_name = "cotação"
        verbose_name_plural = "cotações"
        ordering = ["-data_pregao", "mercado", "categoria"]
        constraints = [
            models.UniqueConstraint(
                fields=["mercado", "categoria", "praca", "data_pregao"],
                name="cotacoes_unica_por_pregao"),
            # choices= é só validação de formulário -- quem grava pelo ORM sem
            # full_clean() passa direto. Lista POR EXTENSO, nunca como delta
            # de CATEGORIAS: é a mesma armadilha que já mordeu esta tarefa
            # uma vez (a spec original tinha perdido 'bezerro' assim).
            models.CheckConstraint(
                condition=models.Q(categoria__in=[
                    "boi", "novilha", "vaca", "desmama", "bezerro", "garrote",
                    "boi magro", "bezerra", "vaca magra",
                ]),
                name="cotacoes_categoria_valida"),
            # Cada mercado preenche o seu lado e deixa o outro vazio. Sem isto
            # uma linha de reposicao sem rs_kg entra e vira preco None na tela.
            models.CheckConstraint(
                condition=(
                    models.Q(mercado="abate", unidade="arroba",
                             bruto_a_vista__isnull=False, rs_kg__isnull=True)
                    | models.Q(mercado="reposicao", unidade="kg",
                               rs_kg__isnull=False, peso_ref_kg__isnull=False,
                               bruto_a_vista__isnull=True)),
                name="cotacoes_unidade_coerente"),
        ]

    def __str__(self):
        return f"{self.get_categoria_display()} — R$ {self.bruto_a_vista} a arroba"

    # A female that is not a novilha is priced off the vaca gorda page -- the
    # closest female quote the market publishes. Same mapping the bot uses.
    PAGINA = {"novilha": NOVILHA, "vaca": VACA, "bezerra": VACA, "femea": VACA}

    ESCADA_MACHO = ("desmama", "bezerro", "garrote", "boi magro")
    ESCADA_FEMEA = ("desmama", "bezerra", "novilha", "vaca magra")
    # Mesmas strings que cotacao_diaria.PRACA_REPOSICAO grava (Tarefa 3). É a
    # praça que separa a desmama macho da desmama fêmea, porque a chave única
    # não tem sexo. As duas pontas têm de concordar literalmente.
    PRACA_REPOSICAO = {"macho": "SP", "femea": "SP-F"}

    @classmethod
    def categoria_de(cls, categoria_ou_sexo):
        """Página de abate correspondente. Só serve ao ABATE.

        A reposição não é endereçável por categoria sozinha -- veja
        `escada_reposicao` e `ultimas_por_categoria`.
        """
        return cls.PAGINA.get(_sem_acento(categoria_ou_sexo), cls.BOI)

    @classmethod
    def mais_recente(cls, categoria_ou_sexo):
        """Latest ABATE quote for one category. Always current -- never memoised.

        Só abate, mesmo motivo de `ultimas_por_categoria`: `categoria_de`
        devolve `novilha` pra novilha e pra fêmea sem categoria, e `novilha`
        existe nos dois mercados. Sem o filtro, uma linha de reposição mais
        recente ganha da de abate -- e ela não tem `bruto_a_vista`
        (CheckConstraint), o que vira campo em branco em `animal.html`.

        There WAS a five-minute memo here, to stop the herd list running one
        query per animal. It was wrong twice over. Gunicorn runs three workers
        and Django's LocMemCache is per PROCESS, so for up to five minutes after
        a new quote two readers could see two different prices for the same
        animal. And a price is precisely the thing that must not be stale by
        design.

        The N+1 is solved properly instead, by `ultimas_por_categoria()`: three
        queries once per request, handed to every animal on the page.
        """
        return cls.objects.filter(
            mercado=cls.ABATE, categoria=cls.categoria_de(categoria_ou_sexo)
        ).order_by("-data_pregao").first()

    @classmethod
    def ultimas_por_categoria(cls):
        """{categoria: última cotação de ABATE} em três queries.

        Só abate: a reposição não é endereçável por categoria sozinha -- a
        mesma `novilha` existe nos dois mercados, e `desmama` existe nos dois
        sexos. Para reposição use `escada_reposicao`.
        """
        return {c: cls.objects.filter(mercado=cls.ABATE, categoria=c)
                              .order_by("-data_pregao").first()
                for c, _ in cls.CATEGORIAS_ABATE}

    @classmethod
    def escada_reposicao(cls, sexo):
        """Os pontos (peso_ref_kg, rs_cabeca) do último pregão, para um sexo."""
        femea = e_femea(sexo)
        cats = cls.ESCADA_FEMEA if femea else cls.ESCADA_MACHO
        praca = cls.PRACA_REPOSICAO["femea" if femea else "macho"]
        pontos = []
        for cat in cats:
            c = (cls.objects.filter(mercado=cls.REPOSICAO, categoria=cat, praca=praca)
                 .order_by("-data_pregao").first())
            if c and c.peso_ref_kg and c.rs_cabeca:
                pontos.append((float(c.peso_ref_kg), float(c.rs_cabeca)))
        return pontos


# --- Proxy models -------------------------------------------------------------
# `compras` and `compradores` each hold two roles in a `tipo` column. Proxies
# give the admin four separate sections -- matching the spreadsheet's tabs --
# without a migration or a data move.


class GerenteCompra(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(tipo=Movimentacao.COMPRA)


class GerenteVenda(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(tipo=Movimentacao.VENDA)


class Compra(Movimentacao):
    objects = GerenteCompra()

    class Meta:
        proxy = True
        verbose_name = "compra"
        verbose_name_plural = "compras"

    def save(self, *args, **kwargs):
        self.tipo = Movimentacao.COMPRA
        return super().save(*args, **kwargs)


class Venda(Movimentacao):
    objects = GerenteVenda()

    class Meta:
        proxy = True
        verbose_name = "venda"
        verbose_name_plural = "vendas"

    def save(self, *args, **kwargs):
        self.tipo = Movimentacao.VENDA
        return super().save(*args, **kwargs)


class GerenteFornecedor(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(tipo=Contraparte.VENDEDOR)


class GerenteComprador(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(tipo=Contraparte.COMPRADOR)


class Fornecedor(Contraparte):
    objects = GerenteFornecedor()

    class Meta:
        proxy = True
        verbose_name = "fornecedor"
        verbose_name_plural = "fornecedores"

    def save(self, *args, **kwargs):
        self.tipo = Contraparte.VENDEDOR
        return super().save(*args, **kwargs)


class Comprador(Contraparte):
    objects = GerenteComprador()

    class Meta:
        proxy = True
        verbose_name = "comprador"
        verbose_name_plural = "compradores"

    def save(self, *args, **kwargs):
        self.tipo = Contraparte.COMPRADOR
        return super().save(*args, **kwargs)

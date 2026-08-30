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
    BEZERRO = "bezerro", "bezerro"
    GARROTE = "garrote", "garrote"
    NOVILHO = "novilho", "novilho"
    BOI = "boi", "boi"
    TOURO = "touro", "touro"
    BEZERRA = "bezerra", "bezerra"
    NOVILHA = "novilha", "novilha"
    VACA = "vaca", "vaca"


# The category settles the sex -- a vaca is never macho. Kept in ONE place so
# the derivation and the coherence check cannot drift apart. This matters in
# money: sex picks the carcass yield (55% vs 45%), so an animal recorded as a
# vaca but flagged macho would be priced about R$ 1.100 too high, quietly.
SEXO_DA_CATEGORIA = {
    Categoria.BEZERRO: Sexo.MACHO,
    Categoria.GARROTE: Sexo.MACHO,
    Categoria.NOVILHO: Sexo.MACHO,
    Categoria.BOI: Sexo.MACHO,
    Categoria.TOURO: Sexo.MACHO,
    Categoria.BEZERRA: Sexo.FEMEA,
    Categoria.NOVILHA: Sexo.FEMEA,
    Categoria.VACA: Sexo.FEMEA,
}


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
    # A deal is priced in one of three ways, and which one depends on who is on
    # the other side. A frigorífico buys by the arroba; a neighbour buys the lot
    # for a round number. Whichever he knows goes in; the rest is derived.
    preco_arroba = models.DecimalField(
        "preço da arroba", max_digits=10, decimal_places=2, blank=True, null=True,
        help_text="Quando o negócio foi fechado por arroba")
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
    # The arroba is not one price per deal. Within a single sale a thin cow --
    # "meia carne" -- fetches less per arroba than a finished one, so the price
    # belongs to the HEAD, with the deal's price as the fallback for the rest.
    preco_arroba_venda = models.DecimalField(
        "preço da arroba desta cabeça", max_digits=10, decimal_places=2,
        blank=True, null=True,
        help_text="Quando esta cabeça saiu por arroba diferente da do negócio "
                  "(magra, meia carne)")

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
        """Fills in the sex from the category, and refuses a contradiction."""
        super().clean()
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

    @staticmethod
    def com_cotacoes(animais):
        """Hands one quote lookup to a whole list of animals.

        Use it whenever you iterate more than one animal: the alternative is a
        query per head.
        """
        cotacoes = Cotacao.ultimas_por_categoria()
        animais = list(animais)
        for a in animais:
            a._cotacoes = cotacoes
        return animais

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

    @property
    def valor_venda_apurado(self):
        """What this head fetched, from whichever fact he actually has.

        He prices a sale in one of four ways, depending on the buyer and on the
        animal:

          1. per head -- "essa saiu por 5.200"
          2. by THIS head's arroba -- a thin cow, "meia carne", goes cheaper
             than the finished ones in the very same deal
          3. by the deal's arroba -- one R$/@ for everything
          4. one number for the lot -- selling to a neighbour

        They are tried in that order, most specific first. What he typed always
        wins over anything derived, so editing a single head later does not get
        silently recomputed away.
        """
        if not self.vendido:
            return None
        if self.valor_venda is not None:
            return self.valor_venda
        preco = self.preco_arroba_venda or self.venda.preco_arroba
        if preco is not None:
            arrobas = self.arrobas_na_venda
            if arrobas is not None:
                return Decimal(str(round(arrobas, 4))) * preco
        return self.venda.valor_por_cabeca

    @property
    def origem_valor_venda(self):
        """Where the sale value came from -- shown so a derived number is never
        mistaken for a recorded one."""
        if not self.vendido:
            return None
        if self.valor_venda is not None:
            return "valor por cabeça"
        preco = self.preco_arroba_venda or self.venda.preco_arroba
        if preco is not None and self.arrobas_na_venda is not None:
            propria = " (arroba desta cabeça)" if self.preco_arroba_venda else ""
            return (f"{self.arrobas_na_venda:.2f} @ × R$ {preco}{propria}"
                    .replace(".", ","))
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
        """ESTIMATE of what this head would fetch, at the reference quote.

        Not a promise, and the screens must not read like one. The quote is SP
        Araçatuba's published average; what he is actually paid is whatever the
        buyer offers, and it varies by buyer and by animal -- a thin cow goes
        for less per arroba than a finished one in the same lot. This number is
        for deciding whether to sell, never for what he will receive.

        A sold animal has a real number instead: `valor_venda_apurado`.
        """

        arrobas, cot = self.peso_arrobas, self.cotacao_atual
        if arrobas is None or cot is None:
            return None
        return Decimal(str(arrobas)) * cot.bruto_a_vista


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

    BOI = "boi"
    NOVILHA = "novilha"
    VACA = "vaca"
    CATEGORIAS = [(BOI, "boi gordo"), (NOVILHA, "novilha"), (VACA, "vaca gorda")]

    categoria = models.CharField("categoria", max_length=16, choices=CATEGORIAS)
    praca = models.TextField("praça")
    data_pregao = models.DateField("data do pregão")
    bruto_a_vista = models.DecimalField("bruto à vista", max_digits=10, decimal_places=2)
    bruto_30d = models.DecimalField("bruto 30 dias", max_digits=10, decimal_places=2)
    coletado_em = models.DateTimeField("coletado em", auto_now_add=True)

    class Meta:
        db_table = "cotacoes"
        verbose_name = "cotação"
        verbose_name_plural = "cotações"
        ordering = ["-data_pregao", "categoria"]
        unique_together = (("categoria", "praca", "data_pregao"),)

    def __str__(self):
        return f"{self.get_categoria_display()} — R$ {self.bruto_a_vista} a arroba"

    # A female that is not a novilha is priced off the vaca gorda page -- the
    # closest female quote the market publishes. Same mapping the bot uses.
    PAGINA = {"novilha": NOVILHA, "vaca": VACA, "bezerra": VACA, "femea": VACA}

    @classmethod
    def categoria_de(cls, categoria_ou_sexo):
        return cls.PAGINA.get(_sem_acento(categoria_ou_sexo), cls.BOI)

    @classmethod
    def mais_recente(cls, categoria_ou_sexo):
        """Latest quote for one category. Always current -- never memoised.

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
            categoria=cls.categoria_de(categoria_ou_sexo)
        ).order_by("-data_pregao").first()

    @classmethod
    def ultimas_por_categoria(cls):
        """{categoria: última cotação} in three queries, whatever the herd size."""
        return {c: cls.objects.filter(categoria=c).order_by("-data_pregao").first()
                for c, _ in cls.CATEGORIAS}


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

"""Domain models for the Batistela cattle operation.

Every table here already existed before Django did -- the bot has been writing
to them for weeks. Migration 0001 therefore mirrors the live schema exactly and
is applied with --fake-initial: Django adopts the tables instead of creating
them. Anything new arrives in later migrations, so the history stays honest.

From here on, schema changes are born as Django migrations. No more hand-applied
psql DDL -- that is how `cotacoes` ended up with no history at all.
"""

from decimal import Decimal

from django.core.cache import cache
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
        if not self.valor or not self.quantidade:
            return None
        return self.valor / self.quantidade


class Animal(models.Model):
    brinco = models.TextField("brinco", unique=True)
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

    class Meta:
        db_table = "animais"
        verbose_name = "animal"
        verbose_name_plural = "animais"
        ordering = ["brinco"]
        # Enforced by the database, not only by the form. The bot writes through
        # the ORM and `save()` does not run `full_clean()`, so a choices field
        # alone would let a typo through. These are the last line.
        constraints = [
            models.CheckConstraint(
                condition=models.Q(sexo__in=Sexo.values) | models.Q(sexo__isnull=True),
                name="animais_sexo_valido"),
            models.CheckConstraint(
                condition=models.Q(categoria__in=Categoria.values)
                | models.Q(categoria__isnull=True),
                name="animais_categoria_valida"),
        ]

    def __str__(self):
        return f"brinco {self.brinco}"

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
        return Cotacao.mais_recente(self.categoria or self.sexo)

    @property
    def valor_atual(self):
        """Live market value of this head.

        The spreadsheet had a single hand-typed price in cell F10. This reads
        the quote the 19:00 cron stored, for THIS animal's category -- a cow is
        not paid the steer price.
        """
        arrobas, cot = self.peso_arrobas, self.cotacao_atual
        if arrobas is None or cot is None:
            return None
        if cot.por_quilo:
            return Decimal(str(arrobas * KG_POR_ARROBA)) * cot.bruto_a_vista
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
    por_quilo = models.BooleanField("cotada por quilo", default=False)
    coletado_em = models.DateTimeField("coletado em", auto_now_add=True)

    class Meta:
        db_table = "cotacoes"
        verbose_name = "cotação"
        verbose_name_plural = "cotações"
        ordering = ["-data_pregao", "categoria"]
        unique_together = (("categoria", "praca", "data_pregao"),)

    def __str__(self):
        unidade = "o quilo" if self.por_quilo else "a arroba"
        return f"{self.get_categoria_display()} — R$ {self.bruto_a_vista} {unidade}"

    # A female that is not a novilha is priced off the vaca gorda page -- the
    # closest female quote the market publishes. Same mapping the bot uses.
    PAGINA = {"novilha": NOVILHA, "vaca": VACA, "bezerra": VACA, "femea": VACA}

    @classmethod
    def categoria_de(cls, categoria_ou_sexo):
        return cls.PAGINA.get(_sem_acento(categoria_ou_sexo), cls.BOI)

    @classmethod
    def mais_recente(cls, categoria_ou_sexo):
        """Latest quote for a category, cached briefly.

        Without the cache this is one query per animal on the herd list -- 300
        head, 300 queries, all asking the same three questions. The quote only
        changes once a day at 19:00, so five minutes of staleness costs nothing.
        """
        chave = f"cotacao:{cls.categoria_de(categoria_ou_sexo)}"
        achado = cache.get(chave)
        if achado is None:
            achado = cls.objects.filter(
                categoria=cls.categoria_de(categoria_ou_sexo)
            ).order_by("-data_pregao").first()
            cache.set(chave, achado, 300)
        return achado


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

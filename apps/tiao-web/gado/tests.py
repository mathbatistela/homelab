"""Tests for the herd site.

House rule, learned the hard way on the app this replaces: a test that asserts
a status code proves nothing. Its predecessor shipped 120 unit tests and 17 e2e
flows, and still served a 404 at the front door and an empty page every evening
-- because every assertion was satisfied by an error page. Everything below
asserts the number or the text a human would look for.
"""

import datetime
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from .models import (
    Animal, Categoria, Compra, Comprador, Contraparte, Cotacao, Despesa,
    Fornecedor, Movimentacao, Pesagem, Propriedade, Sexo, Venda,
)


class BaseGado(TestCase):
    @classmethod
    def setUpTestData(cls):
        # A migration de seed já cria os quatro pastos; get_or_create para o
        # teste não brigar com ela.
        cls.pasto, _ = Propriedade.objects.get_or_create(nome="DOIS IPES")
        cls.leilao = Contraparte.objects.create(nome="Leilão Sirotto",
                                                tipo=Contraparte.VENDEDOR)
        cls.compra = Movimentacao.objects.create(
            tipo=Movimentacao.COMPRA, data=datetime.date(2026, 8, 29),
            valor=Decimal("20910.00"), quantidade=7, comprador=cls.leilao)
        cls.vaca = Animal.objects.create(brinco="2031", categoria="vaca",
                                         sexo="fêmea", propriedade=cls.pasto,
                                         compra=cls.compra)
        cls.boi = Animal.objects.create(brinco="7001", categoria="boi",
                                        sexo="macho", propriedade=cls.pasto)
        for a in (cls.vaca, cls.boi):
            Pesagem.objects.create(animal=a, data=datetime.date(2026, 8, 29),
                                   peso_kg=Decimal("387.00"))
        for cat, preco in (("boi", "338.00"), ("novilha", "328.00"), ("vaca", "318.00")):
            Cotacao.objects.create(categoria=cat, praca="SP Araçatuba",
                                   data_pregao=datetime.date(2026, 8, 28),
                                   bruto_a_vista=Decimal(preco),
                                   bruto_30d=Decimal(preco))



class TestValorAtual(BaseGado):
    """The money. Getting this wrong misprices the whole herd, silently."""

    def test_rendimento_por_sexo(self):
        self.assertEqual(self.vaca.rendimento, 45.0)
        self.assertEqual(self.boi.rendimento, 55.0)

    def test_arroba_e_de_carcaca_nao_de_peso_vivo(self):
        # 387 kg vivo x 45% = 174,15 kg de carcaça / 15 = 11,61 @.
        # Dividir o peso vivo por 15 daria 25,8 @ -- mais que o dobro.
        self.assertAlmostEqual(self.vaca.peso_arrobas, 11.61, places=2)

    def test_vaca_usa_a_cotacao_da_vaca_nao_a_do_boi(self):
        self.assertEqual(self.vaca.cotacao_atual.categoria, Cotacao.VACA)
        self.assertEqual(self.boi.cotacao_atual.categoria, Cotacao.BOI)

    def test_valor_atual_bate_na_conta(self):
        self.assertAlmostEqual(float(self.vaca.valor_atual), 3691.98, places=2)
        # Mesmo peso, sexo diferente: 387 x 55% / 15 x 338 = 4796,22.
        self.assertAlmostEqual(float(self.boi.valor_atual), 4796.22, places=2)

    def test_valor_atual_e_none_sem_pesagem(self):
        novo = Animal.objects.create(brinco="9999", categoria="boi", sexo="macho")
        self.assertIsNone(novo.peso_arrobas)
        self.assertIsNone(novo.valor_atual)



class TestProxies(BaseGado):
    def test_compra_e_venda_nao_se_misturam(self):
        Movimentacao.objects.create(tipo=Movimentacao.VENDA,
                                    data=datetime.date(2026, 8, 30),
                                    valor=Decimal("5000"), quantidade=1)
        self.assertEqual(Compra.objects.count(), 1)
        self.assertEqual(Venda.objects.count(), 1)
        self.assertEqual(Movimentacao.objects.count(), 2)

    def test_salvar_pelo_proxy_carimba_o_tipo(self):
        v = Venda.objects.create(data=datetime.date(2026, 8, 30),
                                 valor=Decimal("100"), quantidade=1)
        self.assertEqual(Movimentacao.objects.get(pk=v.pk).tipo, Movimentacao.VENDA)

    def test_fornecedor_e_comprador_nao_se_misturam(self):
        Contraparte.objects.create(nome="Frigorífico X", tipo=Contraparte.COMPRADOR)
        self.assertEqual(Fornecedor.objects.count(), 1)
        self.assertEqual(Comprador.objects.count(), 1)


class TestPaginasDoPai(BaseGado):
    """Every assertion is a number or a word he would actually look for."""

    def test_raiz_serve_a_boiada_e_nao_404(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        corpo = r.content.decode()
        self.assertIn("2031", corpo)
        self.assertIn("R$ 3.691,98", corpo)
        self.assertIn("11,61 @", corpo)

    def test_lista_mostra_uma_linha_por_cabeca(self):
        corpo = self.client.get("/").content.decode()
        for brinco in ("2031", "7001"):
            self.assertIn(brinco, corpo)

    def test_filtro_de_situacao_realmente_filtra(self):
        venda = Movimentacao.objects.create(tipo=Movimentacao.VENDA,
                                            data=datetime.date(2026, 8, 30))
        self.vaca.venda = venda
        self.vaca.save()
        vendidas = self.client.get("/?situacao=vendido").content.decode()
        self.assertIn("2031", vendidas)
        self.assertNotIn("7001", vendidas)
        pasto = self.client.get("/?situacao=pasto").content.decode()
        self.assertIn("7001", pasto)
        self.assertNotIn(">2031<", pasto)

    def test_ficha_do_animal_diz_a_base_da_conta(self):
        corpo = self.client.get(
            reverse("gado:animal", args=["2031"])).content.decode()
        self.assertIn("Brinco 2031", corpo)
        self.assertIn("R$ 3.691,98", corpo)
        self.assertIn("vaca gorda", corpo)   # de qual cotação veio
        self.assertIn("45", corpo)           # com qual rendimento

    def test_ficha_de_brinco_inexistente_da_404(self):
        self.assertEqual(
            self.client.get(reverse("gado:animal", args=["0000"])).status_code, 404)

    def test_cotacao_mostra_as_tres_categorias(self):
        corpo = self.client.get(reverse("gado:cotacao")).content.decode()
        for preco in ("R$ 338,00", "R$ 328,00", "R$ 318,00"):
            self.assertIn(preco, corpo)

    def test_negocios_mostra_a_compra_e_o_valor_por_cabeca(self):
        corpo = self.client.get(reverse("gado:negocios")).content.decode()
        self.assertIn("Leilão Sirotto", corpo)
        self.assertIn("R$ 20.910,00", corpo)
        self.assertIn("R$ 2.987,14", corpo)   # 20910 / 7

    def test_pagina_vazia_fala_com_ele_em_portugues(self):
        Animal.objects.all().delete()
        corpo = self.client.get("/").content.decode()
        self.assertIn("Nenhuma cabeça", corpo)


class TestDespesas(BaseGado):
    def test_total_de_despesas_soma_por_animal(self):
        for valor in ("86.00", "19.00"):
            Despesa.objects.create(animal=self.vaca, valor=Decimal(valor),
                                   data=datetime.date(2026, 8, 20),
                                   tipo=Despesa.TRANSPORTE)
        self.assertEqual(self.vaca.total_despesas, Decimal("105.00"))
        self.assertEqual(self.boi.total_despesas, Decimal("0"))

    def test_despesa_aparece_na_ficha(self):
        Despesa.objects.create(animal=self.vaca, valor=Decimal("86.00"),
                               data=datetime.date(2026, 8, 20),
                               tipo=Despesa.VETERINARIA, detalhes="vacina")
        corpo = self.client.get(
            reverse("gado:animal", args=["2031"])).content.decode()
        self.assertIn("R$ 86,00", corpo)
        self.assertIn("veterinária", corpo)


class TestConsultas(BaseGado):
    def test_lista_nao_cresce_em_queries_com_o_rebanho(self):
        """The N+1 guard. Without it, 300 head meant 600+ queries."""
        for i in range(20):
            a = Animal.objects.create(brinco=f"T{i}", categoria="boi", sexo="macho")
            Pesagem.objects.create(animal=a, data=datetime.date(2026, 8, 29),
                                   peso_kg=Decimal("400"))
        # The invariant is that the count does not GROW with the herd -- not
        # that it equals some magic number. Asserting the number would break on
        # any harmless change and would not have caught an N+1 anyway.
        with self.assertNumQueries(7):
            self.client.get("/")

        for i in range(60):
            a = Animal.objects.create(brinco=f"U{i}", categoria="boi", sexo="macho")
            Pesagem.objects.create(animal=a, data=datetime.date(2026, 8, 29),
                                   peso_kg=Decimal("400"))
        with self.assertNumQueries(7):   # 22 cabeças ou 82: o mesmo
            self.client.get("/")


class TestEnums(BaseGado):
    """categoria and sexo are closed sets, and they must agree with each other.

    They drive the carcass yield, which drives the price of every head. A vaca
    recorded as macho is not a typo you notice -- it is R$ 1.100 of silent error.
    """

    def test_valores_ficam_em_ascii(self):
        a = Animal.objects.create(brinco="A1", categoria="vaca", sexo="fêmea")
        a.refresh_from_db()
        self.assertEqual(a.sexo, Sexo.FEMEA)
        self.assertEqual(a.sexo, "femea")

    def test_aceita_como_o_bot_escreve(self):
        for entrada, esperado in [("FÊMEA", Sexo.FEMEA), ("f", Sexo.FEMEA),
                                  ("Macho", Sexo.MACHO), ("m", Sexo.MACHO)]:
            a = Animal(brinco=f"B{entrada}", sexo=entrada)
            a.full_clean()
            self.assertEqual(a.sexo, esperado, entrada)

    def test_categoria_preenche_o_sexo_sozinha(self):
        a = Animal.objects.create(brinco="C1", categoria="novilha")
        self.assertEqual(a.sexo, Sexo.FEMEA)
        b = Animal.objects.create(brinco="C2", categoria="garrote")
        self.assertEqual(b.sexo, Sexo.MACHO)

    def test_contradicao_e_recusada(self):
        with self.assertRaises(ValidationError) as caso:
            Animal.objects.create(brinco="D1", categoria="vaca", sexo="macho")
        self.assertIn("sexo", caso.exception.message_dict)

    def test_categoria_desconhecida_e_recusada(self):
        with self.assertRaises(ValidationError):
            Animal.objects.create(brinco="D2", categoria="jumento")

    def test_banco_recusa_mesmo_driblando_o_orm(self):
        """The CHECK is the last line: .update() never calls clean()."""
        a = Animal.objects.create(brinco="E1", categoria="vaca")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Animal.objects.filter(pk=a.pk).update(sexo="jacare")

    def test_rendimento_sai_do_enum(self):
        vaca = Animal.objects.create(brinco="F1", categoria=Categoria.VACA)
        boi = Animal.objects.create(brinco="F2", categoria=Categoria.BOI)
        self.assertEqual(vaca.rendimento, 45.0)
        self.assertEqual(boi.rendimento, 55.0)

    def test_todas_as_categorias_tem_sexo_e_rendimento(self):
        """A new category added without a sex would silently price as male."""
        from .models import SEXO_DA_CATEGORIA
        for cat in Categoria.values:
            self.assertIn(cat, SEXO_DA_CATEGORIA, f"{cat} sem sexo definido")


class TestContaDaArroba(BaseGado):
    """The calculation Jader does on paper every time he weighs an animal."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.vaca.valor_compra = Decimal("2987.14")
        cls.vaca.save()

    def test_pagou_por_arroba(self):
        # 387 kg x 45% / 15 = 11,61 @; 2987,14 / 11,61 = 257,29
        self.assertAlmostEqual(float(self.vaca.pago_por_arroba), 257.29, places=2)

    def test_usa_o_peso_de_ENTRADA_nao_o_de_hoje(self):
        """Dividing by today's weight would understate what he paid.

        The animal put on 100 kg since purchase. Using the current weight makes
        the purchase look cheaper per arroba than it was -- flattering, and wrong.
        """
        Pesagem.objects.create(animal=self.vaca, data=datetime.date(2026, 9, 30),
                               peso_kg=Decimal("487.00"))
        self.assertAlmostEqual(float(self.vaca.arrobas_na_compra), 11.61, places=2)
        self.assertAlmostEqual(float(self.vaca.pago_por_arroba), 257.29, places=2)
        # já o peso de hoje é outro, e é o que vale a venda
        self.assertAlmostEqual(self.vaca.peso_arrobas, 14.61, places=2)

    def test_ganho_por_arroba(self):
        # cotação da vaca 318,00 menos os 257,29 pagos
        self.assertAlmostEqual(float(self.vaca.ganho_por_arroba), 60.71, places=2)

    def test_cotacao_por_arroba_e_o_bruto_a_vista(self):
        """Only SP Araçatuba is collected, and it is quoted per arroba.

        The per-kilo praças are refused by the scraper, so no unit conversion
        can reach this far -- and a conversion that never runs is a branch that
        can only rot.
        """
        self.assertEqual(self.vaca.cotacao_por_arroba, Decimal("318.00"))

    def test_custo_soma_despesas(self):
        Despesa.objects.create(animal=self.vaca, valor=Decimal("100.00"),
                               data=datetime.date(2026, 8, 30), tipo=Despesa.VETERINARIA)
        self.assertEqual(self.vaca.custo_total, Decimal("3087.14"))
        self.assertAlmostEqual(float(self.vaca.ganho), 3691.98 - 3087.14, places=2)

    def test_sem_valor_de_compra_nao_inventa(self):
        self.assertIsNone(self.boi.pago_por_arroba)
        self.assertIsNone(self.boi.custo_total)
        self.assertIsNone(self.boi.ganho)

    def test_a_conta_aparece_na_ficha(self):
        corpo = self.client.get(
            reverse("gado:animal", args=["2031"])).content.decode()
        self.assertIn("Pagou na arroba", corpo)
        self.assertIn("R$ 257,29", corpo)
        self.assertIn("+R$ 60,71", corpo)

    def test_a_conta_aparece_na_lista(self):
        corpo = self.client.get("/").content.decode()
        self.assertIn("Pagou na @", corpo)
        self.assertIn("R$ 257,29", corpo)


class TestTelaCheia(BaseGado):
    """The wide-table mode, checked in the markup.

    Behaviour was verified in a real browser at 390px; what a test can hold is
    the structural invariant that broke it, so it cannot come back.
    """

    def test_botao_fica_dentro_do_painel_que_vai_a_tela_cheia(self):
        """The bug: the browser renders ONLY the fullscreen element and its
        descendants. With the button as a sibling of the table it disappeared on
        entering fullscreen, leaving no visible way out.
        """
        corpo = self.client.get("/").content.decode()
        painel = corpo.index('id="painel-boiada"')
        botao = corpo.index('id="btn-expandir"')
        fim_painel = corpo.index("</table>", painel)
        self.assertLess(painel, botao, "o botão está antes do painel")
        self.assertLess(botao, fim_painel, "o botão caiu fora do painel")

    def test_botao_aciona_o_painel_e_nao_a_tabela(self):
        corpo = self.client.get("/").content.decode()
        self.assertIn("alternarTabela('painel-boiada')", corpo)

    def test_a_pagina_traz_as_tres_camadas(self):
        corpo = self.client.get("/").content.decode()
        self.assertIn("expandido", corpo)          # CSS, funciona em qualquer aparelho
        self.assertIn("requestFullscreen", corpo)  # Android
        self.assertIn("orientation.lock", corpo)   # Android

    def test_coluna_do_brinco_fica_fixa(self):
        corpo = self.client.get("/").content.decode()
        self.assertIn("th:first-child,td:first-child{position:sticky", corpo)


class TestBagunçaInicial(BaseGado):
    """The first weeks are a pile of half-remembered history.

    Purchases never weighed, animals already sold, sales with no weight, cattle
    known only as "the cow with the broken horn" -- all mixed together. A schema
    that refuses these loses the history; the only floor is that an animal must
    stay referable.
    """

    def test_bicho_so_com_referencia(self):
        a = Animal.objects.create(referencia="a vaca do chifre quebrado",
                                  categoria="vaca")
        self.assertIsNone(a.brinco)
        self.assertEqual(a.identificacao, "a vaca do chifre quebrado")

    def test_varios_sem_brinco_convivem(self):
        """NULL is distinct from NULL in Postgres, so unique does not collide."""
        Animal.objects.create(referencia="o boi manso do curral")
        Animal.objects.create(referencia="a bezerra da ponta branca")
        self.assertEqual(Animal.objects.filter(brinco__isnull=True).count(), 2)

    def test_bicho_anonimo_e_recusado(self):
        """The one floor: no tag AND no phrase means it can never be spoken of."""
        with self.assertRaises((IntegrityError, ValidationError)), transaction.atomic():
            Animal.objects.create(categoria="boi")

    def test_comprado_e_nunca_pesado(self):
        a = Animal.objects.create(brinco="T900", categoria="boi",
                                  valor_compra=Decimal("2500"))
        self.assertIsNone(a.peso_atual_kg)
        self.assertIsNone(a.valor_atual)      # sem peso não há valor
        self.assertIsNone(a.pago_por_arroba)  # nem preço por arroba
        self.assertEqual(a.custo_total, Decimal("2500"))   # o que custou, esse sim

    def test_vendido_sem_nunca_ter_pesado(self):
        v = Movimentacao.objects.create(tipo=Movimentacao.VENDA,
                                        data=datetime.date(2026, 8, 1),
                                        valor=Decimal("3000"), quantidade=1)
        a = Animal.objects.create(brinco="T901", categoria="boi", venda=v)
        self.assertIsNotNone(a.venda_id)
        self.assertIsNone(a.valor_atual)

    def test_venda_sem_peso_e_sem_animal_ligado(self):
        """He sold a lot before any of it was in the system."""
        v = Venda.objects.create(data=datetime.date(2026, 7, 1),
                                 valor=Decimal("18000"), quantidade=6)
        self.assertEqual(v.animais_vendidos.count(), 0)
        self.assertAlmostEqual(float(v.valor_por_cabeca), 3000.0)

    def test_faltando_diz_o_que_o_buraco_custa(self):
        a = Animal.objects.create(referencia="a vermelha")
        faltas = " | ".join(a.faltando)
        self.assertIn("brinco", faltas)
        self.assertIn("categoria", faltas)
        self.assertIn("nunca foi pesado", faltas)
        # e o que ela já tem não aparece como falta
        self.assertNotIn("referência", faltas)

    def test_animal_completo_nao_tem_faltas(self):
        self.vaca.valor_compra = Decimal("2987.14")
        self.vaca.save()
        self.assertEqual(self.vaca.faltando, [])

    def test_lista_aguenta_a_mistura(self):
        """The herd page must render with all of this on it at once."""
        Animal.objects.create(referencia="a vaca do chifre quebrado")
        Animal.objects.create(brinco="T900", categoria="boi")
        corpo = self.client.get("/").content.decode()
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertIn("a vaca do chifre quebrado", corpo)
        self.assertIn("T900", corpo)

    def test_ficha_de_bicho_sem_brinco_abre_pelo_id(self):
        a = Animal.objects.create(referencia="o boi manso")
        r = self.client.get(reverse("gado:animal_por_id", args=[a.pk]))
        self.assertEqual(r.status_code, 200)
        corpo = r.content.decode()
        self.assertIn("o boi manso", corpo)
        self.assertIn("Falta anotar", corpo)


class TestVendido(BaseGado):
    """A sold animal is worth what it fetched, not what it would fetch."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.vaca.valor_compra = Decimal("2987.14")
        cls.vaca.save()
        cls.venda = Venda.objects.create(data=datetime.date(2026, 8, 25),
                                         valor=Decimal("10450.00"), quantidade=2)
        cls.vaca.venda = cls.venda
        cls.vaca.save()

    def test_resultado_e_o_que_rendeu_de_verdade(self):
        self.assertEqual(self.vaca.valor_venda, Decimal("5225.00"))
        self.assertAlmostEqual(float(self.vaca.resultado), 5225.00 - 2987.14, places=2)

    def test_resumo_nao_conta_vendido_no_valor_da_boiada(self):
        """Counting a sold animal's hypothetical value inflates the herd."""
        corpo = self.client.get("/").content.decode()
        self.assertIn("Vendidas", corpo)
        # o boi (não vendido) entra; a vaca (vendida) não
        self.assertIn("R$ 4.796,22", corpo)      # valor do boi
        self.assertNotIn("R$ 8.488,20", corpo)   # soma dos dois, se contasse errado

    def test_ficha_do_vendido_mostra_a_venda(self):
        corpo = self.client.get(
            reverse("gado:animal", args=["2031"])).content.decode()
        self.assertIn("Vendida", corpo)
        self.assertIn("R$ 5.225,00", corpo)   # saiu por
        self.assertIn("Valeria hoje", corpo)  # o hipotético, rotulado como tal

    def test_ficha_do_nao_vendido_nao_fala_de_venda(self):
        corpo = self.client.get(
            reverse("gado:animal", args=["7001"])).content.decode()
        self.assertNotIn("Saiu por", corpo)
        self.assertIn("Vale hoje", corpo)

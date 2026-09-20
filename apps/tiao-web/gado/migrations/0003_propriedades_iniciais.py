"""Seeds the four pastures Jader already uses, taken from his spreadsheet.

Seed data, not schema -- but it lives in a migration so a fresh database comes
up usable and nobody has to remember to type them again. New pastures are added
through the admin, not here.
"""

from django.db import migrations

NOMES = ["ARRENDAMENTO 1", "ARRENDAMENTO 2", "DOIS IPES", "PAI E FILHO"]


def semear(apps, schema_editor):
    Propriedade = apps.get_model("gado", "Propriedade")
    for nome in NOMES:
        Propriedade.objects.get_or_create(nome=nome)


def remover(apps, schema_editor):
    Propriedade = apps.get_model("gado", "Propriedade")
    # Only removes pastures with nothing pointing at them.
    Propriedade.objects.filter(nome__in=NOMES, animais__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [("gado", "0002_propriedade_compra_comprador_fornecedor_venda_and_more")]
    operations = [migrations.RunPython(semear, remover)]

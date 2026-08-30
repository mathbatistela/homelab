"""Os pastos de verdade: Sítio Pai e Filho e Sítio II Ypês.

A 0003 semeou quatro nomes tirados da planilha de teste, incluindo dois
"arrendamentos" que não existem. Esta corrige para os dois reais, com a grafia
que o Seu Jader usa -- e a grafia importa: "II" vira "Ii" em qualquer
capitalização automática, e "Ypês" não é "Ipes".

Renomeia em vez de recriar, para não soltar os animais já apontados ao pasto.
"""

from django.db import migrations

RENOMEAR = {"PAI E FILHO": "Sítio Pai e Filho", "DOIS IPES": "Sítio II Ypês"}
REMOVER = ["ARRENDAMENTO 1", "ARRENDAMENTO 2"]


def corrigir(apps, schema_editor):
    Propriedade = apps.get_model("gado", "Propriedade")
    for antigo, novo in RENOMEAR.items():
        Propriedade.objects.filter(nome=antigo).update(nome=novo)
    # Só remove o que não tem bicho apontado -- um pasto com animal nunca é lixo,
    # por mais que o nome pareça errado.
    Propriedade.objects.filter(nome__in=REMOVER, animais__isnull=True).delete()


def desfazer(apps, schema_editor):
    Propriedade = apps.get_model("gado", "Propriedade")
    for antigo, novo in RENOMEAR.items():
        Propriedade.objects.filter(nome=novo).update(nome=antigo)
    for nome in REMOVER:
        Propriedade.objects.get_or_create(nome=nome)


class Migration(migrations.Migration):
    dependencies = [("gado", "0010_texto_arroba_por_cabeca")]
    operations = [migrations.RunPython(corrigir, desfazer)]

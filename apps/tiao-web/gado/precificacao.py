"""Quanto vale uma cabeça, no mercado certo para ela.

Módulo puro de propósito: sem Django, sem banco, sem rede. Entra número, sai
número. A regra que vira dinheiro merece ser testável sozinha.

DUAS REGRAS NASCERAM DE NÚMEROS MEDIDOS, e trocá-las por algo "mais simples"
reintroduz erro em dinheiro:

1. O valor sai de uma CURVA interpolada entre os pontos que a Scot publica,
   nunca do R$/kg da faixa em que o bicho caiu. Usar a faixa produz degraus em
   que o animal vale MENOS ao engordar: -R$ 340 aos 230 kg, -R$ 552 aos 300 kg.
   Engordar é o único trabalho que o Seu Jader faz; a tela não pode chamar isso
   de prejuízo.

2. A troca entre reposição e abate acontece no CRUZAMENTO das duas curvas,
   calculado a cada leitura. Fixar em 345 kg (peso de referência do boi magro)
   recria um degrau de +R$ 240.
"""

# Se o cruzamento calculado cair abaixo disto, algo está errado com alguma das
# duas cotações. Melhor um limiar conservador que bezerro novo virando boi.
PISO_CRUZAMENTO = 250.0

KG_POR_ARROBA = 15.0


def escada(pontos):
    """Ordena e valida os pontos (peso_ref_kg, rs_cabeca) de um sexo."""
    limpos = sorted((float(p), float(v)) for p, v in pontos if p and v)
    if len(limpos) < 2:
        raise ValueError("a curva precisa de pelo menos dois pontos publicados")
    return limpos


def valor_reposicao(kg, pontos):
    """R$ por cabeça, interpolado entre os pontos publicados.

    Abaixo do ponto mais leve, extrapola pelo R$/kg desse ponto -- os bezerros
    mais leves do rebanho têm 139 kg, abaixo dos 180 kg do desmama.
    Acima do ponto mais pesado devolve None: ali quem manda é o abate.
    """
    pts = escada(pontos)
    kg = float(kg)
    if kg <= pts[0][0]:
        return kg * (pts[0][1] / pts[0][0])
    if kg > pts[-1][0]:
        return None
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        if x1 <= kg <= x2:
            return y1 + (y2 - y1) * (kg - x1) / (x2 - x1)
    return None


def valor_abate(kg, rendimento_pct, preco_arroba):
    """R$ por cabeça pela arroba de CARCAÇA. Peso vivo passa pelo rendimento."""
    arrobas = float(kg) * (float(rendimento_pct) / 100.0) / KG_POR_ARROBA
    return arrobas * float(preco_arroba)


def cruzamento(pontos, rendimento_pct, preco_arroba, piso=PISO_CRUZAMENTO):
    """O peso a partir do qual o abate paga mais que a reposição.

    Varre de 100 g em 100 g dentro da faixa publicada. Se as curvas não se
    cruzam ali, a troca fica no ponto mais pesado da escada.
    """
    pts = escada(pontos)
    inicio, fim = int(pts[0][0] * 10), int(pts[-1][0] * 10)
    for decimos in range(inicio, fim + 1):
        kg = decimos / 10.0
        if valor_abate(kg, rendimento_pct, preco_arroba) >= valor_reposicao(kg, pts):
            return max(kg, piso)
    return max(pts[-1][0], piso)

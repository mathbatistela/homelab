"""Gráfico de linha desenhado aqui no servidor, em SVG.

Sem biblioteca de JavaScript, de propósito e por decisão de projeto: o site
não tem nenhuma dependência de front, o CSS mora inline no `base.html`, e
esta tela é lida no 3G do sítio. Um `<svg>` que já vem no HTML não tem
download, não tem espera e não tem o que dar errado quando a rede não ajuda.

O `viewBox` tem largura de CELULAR de propósito. O SVG escala junto com a
caixa, texto incluído: desenhar num quadro de 1100 px e deixar o celular
encolher para 350 reduziria uma fonte de 18 a uns 6 px reais -- ilegível
justamente para quem lê a tela no sol. Desenhando em 380 o texto sai no
tamanho em que foi escrito, e no desktop a folha só cresce até o teto de
largura que o CSS impõe.
"""

from django.utils.html import escape
from django.utils.safestring import mark_safe

from .templatetags.gado_extras import numero

LARGURA = 380
ALTURA = 200
ESQ, DIR, TOPO, BASE = 58, 10, 12, 26     # margens; a esquerda cabe "R$ 15,31"
ALTURA_LEGENDA = 21

TINTA = "#1a1a1a"
FRACA = "#5c5c5c"
LINHA = "#d9d5cd"

# As cores das séries saem da paleta do base.html. Três bastam: o abate tem
# três categorias, e a escada de reposição é lida por peso, não por cor.
CORES = ("#1a1a1a", "#15803d", "#b45309", "#b91c1c")


def _rotulo(v, casas):
    """"R$ 338" na arroba, "R$ 15,31" no quilo.

    Centavos na arroba só gastariam a margem esquerda: a arroba anda em
    reais. No quilo eles são o movimento inteiro.
    """
    return "R$ " + numero(v, casas)


def linha(series, descricao="Como o preço andou"):
    """Desenha as séries e devolve o SVG pronto, ou None se não há o que desenhar.

    `series` é uma lista de {"nome", "cor", "pontos"}, e cada ponto é
    (data, valor). O eixo x é CATEGÓRICO -- um passo por pregão, não por dia:
    pregão não acontece em fim de semana nem em feriado, e um eixo por tempo
    abriria buracos que parecem queda de atividade onde só houve domingo.

    Devolve None com menos de dois pregões. É o estado de hoje da reposição,
    e um gráfico de um ponto só não é gráfico -- a tela diz isso em português
    em vez de desenhar uma linha que não existe.
    """
    series = [s for s in series if s.get("pontos")]
    datas = sorted({d for s in series for d, _ in s["pontos"]})
    if len(datas) < 2:
        return None

    coluna = {d: i for i, d in enumerate(datas)}
    valores = [float(v) for s in series for _, v in s["pontos"]]
    alto, baixo = max(valores), min(valores)
    # Preço parado por quinze pregões é o caso real da novilha. Sem a folga o
    # denominador vira zero e o SVG sai cheio de NaN.
    if alto == baixo:
        alto, baixo = alto + 1, baixo - 1
    casas = 2 if alto < 100 else 0

    larg = LARGURA - ESQ - DIR
    alt = ALTURA - TOPO - BASE
    passo = larg / (len(datas) - 1)

    def x(d):
        return ESQ + coluna[d] * passo

    def y(v):
        return TOPO + (alto - float(v)) / (alto - baixo) * alt

    p = [f'<svg xmlns="http://www.w3.org/2000/svg" role="img" '
         f'viewBox="0 0 {LARGURA} {ALTURA + ALTURA_LEGENDA * len(series)}">'
         f'<title>{escape(descricao)}</title>']

    # Três linhas de grade: o maior, o meio e o menor. Mais do que isso vira
    # ruído numa tela lida de relance.
    for fatia in (0, 0.5, 1):
        valor = alto - (alto - baixo) * fatia
        yy = round(TOPO + alt * fatia, 1)
        p.append(f'<line x1="{ESQ}" y1="{yy}" x2="{LARGURA - DIR}" y2="{yy}" '
                 f'stroke="{LINHA}" stroke-width="1"/>')
        p.append(f'<text x="{ESQ - 6}" y="{yy + 4}" text-anchor="end" '
                 f'font-size="12" fill="{FRACA}">{escape(_rotulo(valor, casas))}</text>')

    # Só a primeira e a última data. Quinze rótulos num celular viram borrão.
    p.append(f'<text x="{ESQ}" y="{ALTURA - 6}" font-size="12" fill="{FRACA}">'
             f'{datas[0]:%d/%m}</text>')
    p.append(f'<text x="{LARGURA - DIR}" y="{ALTURA - 6}" text-anchor="end" '
             f'font-size="12" fill="{FRACA}">{datas[-1]:%d/%m}</text>')

    for i, s in enumerate(series):
        cor = s.get("cor") or CORES[i % len(CORES)]
        pontos = sorted(s["pontos"], key=lambda dv: dv[0])
        traco = " ".join(f"{round(x(d), 1)},{round(y(v), 1)}" for d, v in pontos)
        p.append(f'<polyline points="{traco}" fill="none" stroke="{cor}" '
                 f'stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>')
        # O último ponto marcado: é o preço de hoje, o número que ele procura.
        ud, uv = pontos[-1]
        p.append(f'<circle cx="{round(x(ud), 1)}" cy="{round(y(uv), 1)}" r="4" fill="{cor}"/>')

        base_leg = ALTURA + ALTURA_LEGENDA * i + 12
        p.append(f'<line x1="{ESQ}" y1="{base_leg - 4}" x2="{ESQ + 22}" y2="{base_leg - 4}" '
                 f'stroke="{cor}" stroke-width="3" stroke-linecap="round"/>')
        # Com os centavos, sempre: aqui o número é o preço de hoje e tem de
        # bater com a caixa lá em cima. É só no eixo que arredondar ajuda.
        p.append(f'<text x="{ESQ + 30}" y="{base_leg}" font-size="13" fill="{TINTA}">'
                 f'{escape(s["nome"])} · {escape(_rotulo(float(uv), 2))}</text>')

    p.append("</svg>")
    return mark_safe("".join(p))

"""Diferença dentro da linha.

Uma linha inteira marcada como trocada esconde o que mudou:

    -    total = preco * quantidade + frete
    +    total = preco * quantidade + frete + imposto

Quem lê precisa comparar caractere por caractere com o olho. O mesmo algoritmo
de Myers resolve — só muda a unidade: palavras em vez de linhas.

A separação é o que decide se o resultado é útil. Partir em caracteres dá um
resultado correto e ilegível, porque ele marca letras soltas no meio de
palavras. Partir só por espaço junta pontuação à palavra e faz `frete` e
`frete;` parecerem coisas sem relação nenhuma. O meio-termo usado aqui é
**palavra, espaço ou pontuação**, cada um um item.
"""

from __future__ import annotations

import re

from .myers import Operacao, comparar

#: Uma palavra, um bloco de espaços, ou um caractere de pontuação.
SEPARADOR = re.compile(r"\w+|\s+|[^\w\s]", re.UNICODE)


def separar_palavras(linha: str) -> list[str]:
    """Quebra uma linha em palavras, espaços e pontuação."""
    return SEPARADOR.findall(linha)


def diferenca_de_palavras(antiga: str, nova: str):
    """Compara duas linhas palavra a palavra.

    @returns lista de ``(operacao, texto)``, com os trechos consecutivos de
        mesma operação já juntados — senão sai uma tupla por palavra e por
        espaço, o que é ruído.
    """
    edicoes = comparar(separar_palavras(antiga), separar_palavras(nova))
    juntado: list[list] = []

    for edicao in edicoes:
        if juntado and juntado[-1][0] is edicao.operacao:
            juntado[-1][1] += edicao.linha
        else:
            juntado.append([edicao.operacao, edicao.linha])

    return [(operacao, texto) for operacao, texto in juntado]


def marcar(antiga: str, nova: str, abre: str = "[-", fecha: str = "-]", abre_novo: str = "{+", fecha_novo: str = "+}"):
    """As duas linhas com o que mudou marcado.

    As marcas são as mesmas que o `git diff --word-diff` usa, e por um motivo
    prático: elas funcionam em terminal sem cor, em log e em e-mail. Cor sozinha
    se perde em todos os três.

    @returns ``(antiga_marcada, nova_marcada)``
    """
    partes = diferenca_de_palavras(antiga, nova)
    velha = []
    recente = []

    for operacao, texto in partes:
        if operacao is Operacao.IGUAL:
            velha.append(texto)
            recente.append(texto)
        elif operacao is Operacao.REMOVER:
            velha.append(f"{abre}{texto}{fecha}")
        else:
            recente.append(f"{abre_novo}{texto}{fecha_novo}")

    return "".join(velha), "".join(recente)


def parecidas(antiga: str, nova: str) -> float:
    """O quanto duas linhas se parecem, de 0 a 1.

    Serve para decidir se vale a pena mostrar a diferença por palavra: duas
    linhas que não têm nada em comum ficam mais legíveis como troca inteira do
    que salpicadas de marcas.
    """
    # Espaço em branco fica de fora da conta. Duas linhas sem nada a ver uma
    # com a outra, mas com a mesma indentação, dividem todos os espaços — e
    # `aaaa bbbb cccc` contra `zzzz yyyy xxxx` dava 0,4 de semelhança por
    # causa de dois espaços, o bastante para marcar palavra a palavra duas
    # linhas que não têm palavra nenhuma em comum.
    a = [item for item in separar_palavras(antiga) if item.strip()]
    b = [item for item in separar_palavras(nova) if item.strip()]

    if not a and not b:
        return 1.0 if antiga == nova else 0.0

    if not a or not b:
        return 0.0

    iguais = sum(1 for e in comparar(a, b) if e.operacao is Operacao.IGUAL)

    return 2 * iguais / (len(a) + len(b))

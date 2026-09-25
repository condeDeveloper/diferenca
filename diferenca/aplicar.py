"""Aplicar um diff de volta — a outra metade, e a que prova a primeira.

Gerar um diff é fácil de acreditar que está certo: a saída parece boa. Aplicar
é o que não deixa mentir, porque o resultado tem de ser **exatamente** o outro
arquivo, byte a byte.

Ler um patch tem um cuidado que não é óbvio: **a contagem do cabeçalho não é
confiável e o conteúdo é**. Um patch editado à mão, ou gerado por ferramenta
que arredonda, traz `@@ -10,7 +10,8 @@` com oito linhas embaixo. Confiar na
contagem faz o resto do arquivo escorregar em silêncio; conferir as duas coisas
e reclamar é o que separa um aplicador de um gerador de estrago.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .unificado import SEM_QUEBRA, separar

#: `@@ -10,7 +12,8 @@ contexto`
CABECALHO = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?: (.*))?$")


class ErroDePatch(Exception):
    """O patch não pôde ser lido ou não bate com o arquivo."""

    def __init__(self, mensagem: str, linha: int | None = None):
        super().__init__(mensagem if linha is None else f"linha {linha}: {mensagem}")
        self.linha = linha


@dataclass
class TrechoLido:
    """Um trecho vindo de um patch."""

    inicio_antigo: int
    quantas_antigas: int
    inicio_novo: int
    quantas_novas: int
    linhas: list[tuple[str, str]]
    secao: str = ""


def ler(patch: str) -> list[TrechoLido]:
    """Lê um diff unificado e devolve os trechos.

    Ignora as linhas `---`, `+++` e qualquer cabeçalho que o git põe antes
    (`diff --git`, `index`, `new file mode`), porque um patch de verdade quase
    nunca chega só com os `@@`.
    """
    trechos: list[TrechoLido] = []
    atual: TrechoLido | None = None

    linhas_do_patch = patch.split("\n")

    # `split` deixa um "" no fim quando o texto termina com quebra, e esse ""
    # não é uma linha do patch. Sem tirá-lo, a tolerância a linha de contexto
    # sem o espaço (logo abaixo) o adota como conteúdo e a conferência de
    # contagem acusa uma linha a mais em todo patch bem-formado.
    if linhas_do_patch and linhas_do_patch[-1] == "":
        linhas_do_patch.pop()

    for numero, linha in enumerate(linhas_do_patch, start=1):
        casou = CABECALHO.match(linha)

        if casou:
            atual = TrechoLido(
                inicio_antigo=int(casou.group(1)),
                quantas_antigas=int(casou.group(2)) if casou.group(2) is not None else 1,
                inicio_novo=int(casou.group(3)),
                quantas_novas=int(casou.group(4)) if casou.group(4) is not None else 1,
                linhas=[],
                secao=casou.group(5) or "",
            )

            trechos.append(atual)
            continue

        if atual is None:
            continue

        if linha.startswith(SEM_QUEBRA):
            atual.linhas.append(("\\", ""))
        elif linha[:1] in (" ", "-", "+"):
            atual.linhas.append((linha[0], linha[1:]))
        elif linha == "":
            # Uma linha vazia dentro de um trecho é uma linha de contexto que
            # perdeu o espaço — muitos clientes de e-mail fazem isso. Tratar
            # como fim do trecho perderia conteúdo em silêncio.
            atual.linhas.append((" ", ""))
        else:
            atual = None

    if not trechos:
        raise ErroDePatch("nenhum trecho @@ encontrado no patch")

    for numero, trecho in enumerate(trechos, start=1):
        antigas = sum(1 for tipo, _ in trecho.linhas if tipo in " -")
        novas = sum(1 for tipo, _ in trecho.linhas if tipo in " +")

        if antigas != trecho.quantas_antigas or novas != trecho.quantas_novas:
            raise ErroDePatch(
                f"o trecho {numero} diz {trecho.quantas_antigas} linha(s) antiga(s) e "
                f"{trecho.quantas_novas} nova(s), mas traz {antigas} e {novas}"
            )

    return trechos


def aplicar(antigo: str, patch: str) -> str:
    """Aplica um diff unificado a um texto.

    @param antigo o conteúdo original
    @param patch o diff unificado
    @returns o conteúdo resultante
    @raises ErroDePatch quando o contexto não bate
    """
    linhas, quebra_final = separar(antigo)
    trechos = ler(patch)

    saida: list[str] = []
    posicao = 0
    falta_quebra_no_novo = False

    for numero, trecho in enumerate(trechos, start=1):
        alvo = trecho.inicio_antigo - 1 if trecho.quantas_antigas else trecho.inicio_antigo

        if alvo < posicao:
            raise ErroDePatch(f"o trecho {numero} volta para trás, para a linha {alvo + 1}")

        if alvo > len(linhas):
            raise ErroDePatch(
                f"o trecho {numero} começa na linha {alvo + 1}, além do fim do arquivo "
                f"({len(linhas)} linhas)"
            )

        saida.extend(linhas[posicao:alvo])
        posicao = alvo

        anterior = " "

        for tipo, conteudo in trecho.linhas:
            if tipo == "\\":
                # A marca descreve a linha **imediatamente acima** dela, e só
                # o lado daquela linha. Depois de um `-` ela fala do arquivo
                # antigo e não diz nada sobre o resultado; depois de um `+` ou
                # de uma linha de contexto, fala do novo.
                #
                # Tratar as duas iguais faz o caso "só a quebra final mudou"
                # sair errado justamente nos dois sentidos em que ele importa.
                if anterior in " +":
                    falta_quebra_no_novo = True

                continue

            anterior = tipo

            if tipo in " -":
                if posicao >= len(linhas):
                    raise ErroDePatch(f"o trecho {numero} passa do fim do arquivo")

                if linhas[posicao] != conteudo:
                    raise ErroDePatch(
                        f"o trecho {numero} não bate na linha {posicao + 1}: "
                        f"esperava {conteudo!r}, achei {linhas[posicao]!r}"
                    )

                posicao += 1

            if tipo in " +":
                saida.append(conteudo)

    sobrou_cauda = posicao < len(linhas)

    saida.extend(linhas[posicao:])

    if not saida:
        return ""

    # Se sobrou cauda, a última linha do resultado veio inalterada do original
    # e a quebra final é a que o original tinha. Se nenhum trecho deixou cauda,
    # quem manda é a marca — e só a que descreve o lado novo, porque a do lado
    # antigo fala de um arquivo que está sendo substituído.
    sem_quebra_no_fim = (not quebra_final) if sobrou_cauda else falta_quebra_no_novo

    return "\n".join(saida) + ("" if sem_quebra_no_fim else "\n")


def reverter(novo: str, patch: str) -> str:
    """Desfaz um patch: aplica ele ao contrário.

    Trocar `-` por `+` e as contagens de lugar é tudo que um patch reverso é —
    e é assim que o `patch -R` e o `git apply -R` funcionam.
    """
    invertidos = []

    for linha in patch.split("\n"):
        casou = CABECALHO.match(linha)

        if casou:
            antigo = casou.group(1) + ("," + casou.group(2) if casou.group(2) else "")
            nova = casou.group(3) + ("," + casou.group(4) if casou.group(4) else "")
            resto = f" {casou.group(5)}" if casou.group(5) else ""

            invertidos.append(f"@@ -{nova} +{antigo} @@{resto}")
        elif linha.startswith("-"):
            invertidos.append("+" + linha[1:])
        elif linha.startswith("+"):
            invertidos.append("-" + linha[1:])
        else:
            invertidos.append(linha)

    return aplicar(novo, "\n".join(invertidos))

"""O formato unificado — o que sai do `git diff` e entra no `patch`.

O formato parece simples e tem quatro armadilhas que só aparecem quando se
compara a saída com a de uma ferramenta de verdade:

1. **O cabeçalho de trecho conta em base 1**, mas um arquivo vazio começa em
   **0**. `@@ -0,0 +1,3 @@` é um arquivo criado; `@@ -1,0 ...` não existe.
2. **Contagem 1 é omitida.** `@@ -5 +5,2 @@`, não `@@ -5,1 +5,2 @@`. Quem
   sempre escreve a vírgula gera um diff que o `patch` aceita e que não bate
   byte a byte com o do git.
3. **Trechos que se encostam precisam virar um só.** Com três linhas de
   contexto, duas mudanças a cinco linhas de distância compartilham contexto —
   emitir dois trechos repetiria linhas e o `patch` recusaria.
4. **O arquivo sem quebra de linha no fim** ganha uma linha
   `\\ No newline at end of file`, que pertence ao lado em que falta — e pode
   faltar num lado só.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .myers import Edicao, Operacao, comparar, remocoes_antes

#: Quantas linhas iguais acompanham cada mudança. Três é o costume, e é o que
#: o git e o diff do GNU usam por omissão.
CONTEXTO_PADRAO = 3

#: A marca que o formato usa quando falta a quebra de linha final.
SEM_QUEBRA = "\\ No newline at end of file"


@dataclass
class Trecho:
    """Um `@@ ... @@` e as linhas dele."""

    inicio_antigo: int
    inicio_novo: int
    edicoes: list[Edicao] = field(default_factory=list)

    @property
    def linhas_antigas(self) -> int:
        return sum(1 for e in self.edicoes if e.operacao is not Operacao.INSERIR)

    @property
    def linhas_novas(self) -> int:
        return sum(1 for e in self.edicoes if e.operacao is not Operacao.REMOVER)

    def cabecalho(self, secao: str = "") -> str:
        """A linha `@@ -a,b +c,d @@`."""
        antigo = _intervalo(self.inicio_antigo, self.linhas_antigas)
        novo = _intervalo(self.inicio_novo, self.linhas_novas)
        marca = f"@@ -{antigo} +{novo} @@"

        return f"{marca} {secao}" if secao else marca


def _intervalo(inicio: int, quantas: int) -> str:
    """`5,3`, ou só `5` quando é uma linha, ou `8,0` quando não há nenhuma."""
    return f"{inicio}" if quantas == 1 else f"{inicio},{quantas}"


def secao(linhas, antes_de: int) -> str:
    """O texto que o git escreve **depois** do segundo `@@`.

    Não é comentário nem enfeite: é a linha que o git julga ser a declaração
    dentro da qual a mudança caiu — a função, a classe, a seção. É o que
    permite ler um diff grande sem abrir o arquivo.

    A regra padrão do git é despretensiosa e funciona surpreendentemente bem
    em quase toda linguagem: subindo a partir da linha anterior ao trecho, a
    primeira linha que **começa com letra, `_` ou `$`**. Como corpo de função
    vem indentado e linha em branco não começa com letra, o que sobra é
    justamente a declaração mais recente.
    """
    for i in range(antes_de - 1, -1, -1):
        linha = linhas[i]

        if linha and (linha[0].isalpha() or linha[0] in "_$"):
            return linha.rstrip()

    return ""


def separar(texto: str) -> tuple[list[str], bool]:
    """Separa um texto em linhas, dizendo se ele termina com quebra.

    `splitlines()` sozinho perde essa informação, e ela muda a saída: um
    arquivo sem quebra final ganha uma linha própria no diff.
    """
    if texto == "":
        return [], True

    termina_com_quebra = texto.endswith("\n")
    linhas = texto.split("\n")

    if termina_com_quebra:
        linhas.pop()

    return linhas, termina_com_quebra


def trechos(edicoes, contexto: int = CONTEXTO_PADRAO) -> list[Trecho]:
    """Agrupa as edições em trechos, com o contexto pedido.

    Trechos que se encostariam são unidos, porque emitir os dois repetiria
    linhas de contexto e produziria um patch inválido.
    """
    if contexto < 0:
        raise ValueError(f"o contexto não pode ser negativo: {contexto}")

    mudancas = [i for i, e in enumerate(edicoes) if e.operacao is not Operacao.IGUAL]

    if not mudancas:
        return []

    faixas: list[list[int]] = []

    for i in mudancas:
        comeco = max(0, i - contexto)
        fim = min(len(edicoes), i + contexto + 1)

        # `<=` e não `<`: faixas que apenas se encostam também viram uma só,
        # senão a última linha de contexto de uma é a primeira da outra.
        if faixas and comeco <= faixas[-1][1]:
            faixas[-1][1] = max(faixas[-1][1], fim)
        else:
            faixas.append([comeco, fim])

    resultado = []

    for comeco, fim in faixas:
        pedaco = edicoes[comeco:fim]

        # O início vem da **posição**, não da primeira linha presente. Um
        # trecho de remoção pura não tem nenhuma linha do lado novo, e tirar o
        # número de uma linha que não existe dá zero — quando o certo é "logo
        # depois da última linha nova que já saiu". Só aparece com `-U0`, e é
        # aí que fica claro que contar é o jeito certo nos dois casos.
        consumidas_antigas = sum(
            1 for e in edicoes[:comeco] if e.operacao is not Operacao.INSERIR
        )

        consumidas_novas = sum(
            1 for e in edicoes[:comeco] if e.operacao is not Operacao.REMOVER
        )

        trecho = Trecho(inicio_antigo=0, inicio_novo=0, edicoes=list(pedaco))

        trecho.inicio_antigo = consumidas_antigas + (1 if trecho.linhas_antigas else 0)
        trecho.inicio_novo = consumidas_novas + (1 if trecho.linhas_novas else 0)

        resultado.append(trecho)

    return resultado


def _partir_onde_a_quebra_diverge(
    edicoes, linhas_antigas, linhas_novas, quebra_antiga, quebra_nova
):
    """Parte em remoção + inserção a linha cuja quebra final difere entre os lados.

    Uma linha de contexto é uma só, e ela **não tem como** faltar quebra de um
    lado e ter do outro — o formato unificado não sabe dizer isso. Quando
    acontece, a linha precisa deixar de ser contexto.

    Acontece em dois casos, e não só no óbvio: quando só a quebra final mudou,
    e quando a última linha do arquivo antigo (sem quebra) continua existindo
    no novo com conteúdo depois dela — aí ela **ganhou** uma quebra, mesmo sem
    ninguém ter mexido no texto dela.

    A saída do git para esse caso é uma remoção seguida de uma inserção da
    mesma linha, com a marca no lado a que ela pertence::

        -tres
        \\ No newline at end of file
        +tres

    Sem isto, o diff sai sem mudança nenhuma e aplicá-lo devolve o arquivo com
    a quebra errada — um diff que mente em silêncio.
    """
    ultima_antiga = len(linhas_antigas) - 1
    ultima_nova = len(linhas_novas) - 1

    def tem_quebra(edicao) -> tuple[bool, bool]:
        """Se a linha termina com quebra em cada um dos dois arquivos.

        Só a última linha de um arquivo pode não ter: qualquer outra tem, por
        definição, porque é a quebra que a separa da seguinte.
        """
        no_antigo = edicao.antiga != ultima_antiga or quebra_antiga
        no_novo = edicao.nova != ultima_nova or quebra_nova

        return no_antigo, no_novo

    saida = []

    for edicao in edicoes:
        if edicao.operacao is Operacao.IGUAL:
            no_antigo, no_novo = tem_quebra(edicao)

            if no_antigo != no_novo:
                saida.append(Edicao(Operacao.REMOVER, edicao.linha, edicao.antiga, None))
                saida.append(Edicao(Operacao.INSERIR, edicao.linha, None, edicao.nova))
                continue

        saida.append(edicao)

    # A partição criou remoções e inserções novas no meio de blocos que já
    # estavam ordenados, então a ordem precisa ser refeita — senão um `-` sai
    # depois de um `+` no mesmo bloco e o diff deixa de ser o que o git escreve.
    return remocoes_antes(saida)


def unificado(
    antigo: str,
    novo: str,
    caminho_antigo: str = "a",
    caminho_novo: str = "b",
    contexto: int = CONTEXTO_PADRAO,
    com_secao: bool = True,
) -> str:
    """O diff unificado entre dois textos.

    @param antigo o conteúdo antigo, inteiro
    @param novo o conteúdo novo, inteiro
    @param caminho_antigo o que vai na linha `---`
    @param caminho_novo o que vai na linha `+++`
    @param contexto quantas linhas iguais acompanham cada mudança
    @param com_secao se escreve a declaração de contexto depois do `@@`
    @returns o diff, ou texto vazio quando não há diferença
    """
    linhas_antigas, quebra_antiga = separar(antigo)
    linhas_novas, quebra_nova = separar(novo)

    edicoes = comparar(linhas_antigas, linhas_novas)
    edicoes = _partir_onde_a_quebra_diverge(
        edicoes, linhas_antigas, linhas_novas, quebra_antiga, quebra_nova
    )
    agrupados = trechos(edicoes, contexto)

    if not agrupados:
        return ""

    saida = [f"--- {caminho_antigo}", f"+++ {caminho_novo}"]

    ultima_antiga = len(linhas_antigas) - 1
    ultima_nova = len(linhas_novas) - 1

    for trecho in agrupados:
        # De onde subir para achar a declaração: da linha anterior à primeira
        # do trecho. Num trecho de inserção pura não há "primeira linha
        # antiga", e `inicio_antigo` já é a linha depois da qual se insere —
        # então ela mesma é o ponto de partida, e não a anterior.
        antes = trecho.inicio_antigo - 1 if trecho.linhas_antigas else trecho.inicio_antigo
        onde = secao(linhas_antigas, antes) if com_secao else ""

        saida.append(trecho.cabecalho(onde))

        for edicao in trecho.edicoes:
            saida.append(str(edicao))

            # A marca de "sem quebra no fim" pertence ao lado em que falta, e
            # vem logo depois da linha a que se refere.
            falta_no_antigo = (
                not quebra_antiga
                and edicao.antiga == ultima_antiga
                and edicao.operacao is not Operacao.INSERIR
            )

            falta_no_novo = (
                not quebra_nova
                and edicao.nova == ultima_nova
                and edicao.operacao is not Operacao.REMOVER
            )

            if falta_no_antigo or falta_no_novo:
                saida.append(SEM_QUEBRA)

    return "\n".join(saida) + "\n"

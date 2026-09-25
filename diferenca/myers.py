"""O algoritmo de Myers, em espaço linear.

É o algoritmo que o `git diff`, o `diff` do GNU e o `difflib` do Python usam,
e ele sai de uma mudança de pergunta.

**A pergunta ingênua** é "qual a maior subsequência comum entre os dois
arquivos". Ela se resolve com uma tabela de programação dinâmica de N×M células.
Para dois arquivos de dez mil linhas isso são **cem milhões de células** — e o
tempo de preencher todas elas, mesmo quando os arquivos diferem em uma linha só.

**A pergunta de Myers** é "qual o menor número de edições". Chamando esse número
de D, o algoritmo é O((N+M)·D). A troca é boa porque, em diff de código, **D é
pequeno**: arquivos parecidos é o caso comum, não o excepcional. Um commit que
muda três linhas de um arquivo de dez mil tem D = 6.

A ideia geométrica: imagine um grid em que andar para a direita é apagar uma
linha de `a`, andar para baixo é inserir uma linha de `b`, e andar na diagonal
é uma linha igual — de graça. O caminho de menor custo do canto superior
esquerdo ao inferior direito é o diff. Myers explora esse grid por
**diagonais**, uma frente de onda por vez, e a primeira frente que alcança o
canto tem o D mínimo.

Guardar toda a frente de onda para reconstruir o caminho custa O(D²) de
memória. A refinação em espaço linear, que é a implementada aqui, procura o
**ponto do meio** do caminho avançando das duas pontas ao mesmo tempo até que
as frentes se cruzem, e então resolve as duas metades por recursão. A memória
cai para O(N+M).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Operacao(Enum):
    """O que fazer com uma linha."""

    IGUAL = " "
    REMOVER = "-"
    INSERIR = "+"


@dataclass(frozen=True)
class Edicao:
    """Uma linha do resultado.

    Guarda as duas posições porque o formato unificado precisa das duas: o
    cabeçalho de trecho conta linhas do arquivo antigo **e** do novo, e uma
    edição só sabe responder por si mesma se souber de onde veio.

    Em ``INSERIR`` não há posição no antigo, e em ``REMOVER`` não há no novo.
    """

    operacao: Operacao
    linha: str
    antiga: int | None
    nova: int | None

    def __str__(self) -> str:
        return f"{self.operacao.value}{self.linha}"


def _serpente(a, b, i, j, limite_i, limite_j) -> int:
    """Quantos passos dá para andar na diagonal a partir de (i, j).

    A "serpente" é o trecho de graça: linhas iguais não custam edição, então o
    caminho desliza por elas sem gastar. É onde o algoritmo ganha o tempo dele.
    """
    passos = 0

    while i + passos < limite_i and j + passos < limite_j and a[i + passos] == b[j + passos]:
        passos += 1

    return passos


def _meio(a, b, i0, i1, j0, j1):
    """Acha o ponto do meio do caminho ótimo entre dois trechos.

    Avança uma frente de onda do começo e outra do fim. Quando elas se
    sobrepõem, o ponto de encontro está no caminho de menor custo — e as duas
    metades podem ser resolvidas por recursão, sem guardar o caminho inteiro.

    @returns ``(i_inicio, j_inicio, i_fim, j_fim, d)`` — o trecho do meio e o
        custo total do caminho.
    """
    n = i1 - i0
    m = j1 - j0
    delta = n - m
    impar = delta % 2 != 0
    teto = (n + m + 1) // 2

    # As frentes são indexadas por diagonal. A diagonal em si vai de -m a +n,
    # mas os índices consultados vão além disso: `k` chega a ±teto e o
    # cruzamento consulta `delta - k`. Dimensionar pelo intervalo real das
    # diagonais estoura o vetor — foi o primeiro defeito deste arquivo, e ele
    # só aparece quando os dois lados têm tamanhos bem diferentes.
    deslocamento = n + m + 1
    frente = [0] * (2 * (n + m) + 3)
    tras = [0] * (2 * (n + m) + 3)

    frente[deslocamento + 1] = 0
    tras[deslocamento + 1] = 0

    for d in range(teto + 1):
        # Frente de ida: da diagonal -d até +d, de duas em duas.
        for k in range(-d, d + 1, 2):
            indice = deslocamento + k

            if k == -d or (k != d and frente[indice - 1] < frente[indice + 1]):
                x = frente[indice + 1]
            else:
                x = frente[indice - 1] + 1

            y = x - k
            inicio_x, inicio_y = x, y
            avanco = _serpente(a, b, i0 + x, j0 + y, i1, j1)

            x += avanco
            y += avanco
            frente[indice] = x

            # O encontro só pode acontecer na paridade certa: com delta ímpar,
            # a frente de ida cruza a de volta; com delta par, o contrário.
            if impar and -(k - delta) >= -(d - 1) and -(k - delta) <= d - 1:
                if x + tras[deslocamento + (delta - k)] >= n:
                    return (i0 + inicio_x, j0 + inicio_y, i0 + x, j0 + y, 2 * d - 1)

        # Frente de volta, andando do canto oposto.
        for k in range(-d, d + 1, 2):
            indice = deslocamento + k

            if k == -d or (k != d and tras[indice - 1] < tras[indice + 1]):
                x = tras[indice + 1]
            else:
                x = tras[indice - 1] + 1

            y = x - k
            inicio_x, inicio_y = x, y

            while x < n and y < m and a[i1 - x - 1] == b[j1 - y - 1]:
                x += 1
                y += 1

            tras[indice] = x

            if not impar and -(k - delta) >= -d and -(k - delta) <= d:
                if x + frente[deslocamento + (delta - k)] >= n:
                    return (i1 - x, j1 - y, i1 - inicio_x, j1 - inicio_y, 2 * d)

    # Inalcançável: uma das condições acima sempre dispara em `teto` passos.
    raise AssertionError("o caminho mínimo não foi encontrado")


def _caminho(a, b, i0, i1, j0, j1, saida) -> None:
    """Resolve um trecho, por divisão e conquista."""
    n = i1 - i0
    m = j1 - j0

    if n > 0 and m > 0:
        meio_i0, meio_j0, meio_i1, meio_j1, d = _meio(a, b, i0, i1, j0, j1)

        if d > 1:
            _caminho(a, b, i0, meio_i0, j0, meio_j0, saida)
            saida.extend(("=", i, j) for i, j in _diagonal(meio_i0, meio_j0, meio_i1, meio_j1))
            _caminho(a, b, meio_i1, i1, meio_j1, j1, saida)

            return

        # d <= 1: sobrou no máximo uma edição no trecho inteiro.
        #
        # A tentação aqui é supor que essa única edição está na ponta e emitir
        # a diagonal antes dela. Está errado: ela pode estar em qualquer lugar,
        # e supor a ponta produz um roteiro com a **contagem certa** e o
        # **conteúdo trocado** — que é o pior tipo de defeito, porque a
        # distância mínima continua batendo e só a reconstrução denuncia.
        #
        # Com exatamente uma edição, um lado é o outro com um elemento a menos.
        # O ponto da edição é onde eles divergem pela primeira vez.
        if m > n:
            p = 0

            while p < n and a[i0 + p] == b[j0 + p]:
                p += 1

            saida.extend(("=", i0 + k, j0 + k) for k in range(p))
            saida.append(("+", None, j0 + p))
            saida.extend(("=", i0 + p + k, j0 + p + 1 + k) for k in range(n - p))
        elif n > m:
            p = 0

            while p < m and a[i0 + p] == b[j0 + p]:
                p += 1

            saida.extend(("=", i0 + k, j0 + k) for k in range(p))
            saida.append(("-", i0 + p, None))
            saida.extend(("=", i0 + p + 1 + k, j0 + p + k) for k in range(m - p))
        else:
            saida.extend(("=", i0 + k, j0 + k) for k in range(n))

        return

    # Um dos lados acabou: o que sobra é tudo remoção ou tudo inserção.
    saida.extend(("-", i, None) for i in range(i0, i1))
    saida.extend(("+", None, j) for j in range(j0, j1))


def _diagonal(i0, j0, i1, j1):
    """Os pares de posições de um trecho diagonal."""
    return zip(range(i0, i1), range(j0, j1))


def comparar(antigo, novo) -> list[Edicao]:
    """Compara duas sequências de linhas e devolve o roteiro de edição.

    @param antigo as linhas do arquivo antigo
    @param novo as linhas do arquivo novo
    @returns a lista de edições, na ordem em que aparecem
    """
    a = list(antigo)
    b = list(novo)

    # Os iguais das pontas não precisam de algoritmo nenhum. Aparar antes
    # encolhe o problema e, em diff de código, costuma encolher muito: a maior
    # parte de um arquivo não mudou.
    inicio = 0
    limite = min(len(a), len(b))

    while inicio < limite and a[inicio] == b[inicio]:
        inicio += 1

    fim = 0

    while fim < limite - inicio and a[len(a) - fim - 1] == b[len(b) - fim - 1]:
        fim += 1

    passos: list[tuple] = []

    _caminho(a, b, inicio, len(a) - fim, inicio, len(b) - fim, passos)

    edicoes = [
        Edicao(Operacao.IGUAL, a[i], i, i)
        for i in range(inicio)
    ]

    for tipo, i, j in passos:
        if tipo == "=":
            edicoes.append(Edicao(Operacao.IGUAL, a[i], i, j))
        elif tipo == "-":
            edicoes.append(Edicao(Operacao.REMOVER, a[i], i, None))
        else:
            edicoes.append(Edicao(Operacao.INSERIR, b[j], None, j))

    edicoes.extend(
        Edicao(Operacao.IGUAL, a[len(a) - fim + k], len(a) - fim + k, len(b) - fim + k)
        for k in range(fim)
    )

    return remocoes_antes(edicoes)


def remocoes_antes(edicoes: list[Edicao]) -> list[Edicao]:
    """Põe as remoções antes das inserções dentro de cada bloco de mudança.

    O caminho que o algoritmo acha pode intercalar `+` e `-` — são todos
    caminhos de custo mínimo e ele não tem motivo para preferir um. Mas toda
    ferramenta de diff mostra o bloco com as remoções primeiro, e quem lê conta
    com isso.

    A troca é segura porque acontece dentro de um trecho sem nenhuma linha
    igual: a ordem relativa das remoções entre si e das inserções entre si não
    muda, então os dois lados continuam se reconstruindo.
    """
    saida: list[Edicao] = []
    bloco: list[Edicao] = []

    def despejar():
        saida.extend(e for e in bloco if e.operacao is Operacao.REMOVER)
        saida.extend(e for e in bloco if e.operacao is Operacao.INSERIR)
        bloco.clear()

    for edicao in edicoes:
        if edicao.operacao is Operacao.IGUAL:
            despejar()
            saida.append(edicao)
        else:
            bloco.append(edicao)

    despejar()

    return saida


def distancia(antigo, novo) -> int:
    """O número mínimo de edições — o D do algoritmo.

    É o que dá para conferir contra uma conta independente: o comprimento da
    maior subsequência comum determina D sozinho, por
    ``D = (N - L) + (M - L)``.
    """
    return sum(1 for e in comparar(antigo, novo) if e.operacao is not Operacao.IGUAL)


def blocos_iguais(antigo, novo):
    """Os trechos que os dois lados têm em comum, como ``(i, j, tamanho)``.

    É a mesma forma que o ``difflib.SequenceMatcher.get_matching_blocks``
    devolve, sem o sentinela do fim — o que permite comparar os dois lado a
    lado num teste.
    """
    blocos = []
    atual = None

    for edicao in comparar(antigo, novo):
        if edicao.operacao is Operacao.IGUAL:
            if atual is None:
                atual = [edicao.antiga, edicao.nova, 0]

            atual[2] += 1
        elif atual is not None:
            blocos.append(tuple(atual))
            atual = None

    if atual is not None:
        blocos.append(tuple(atual))

    return blocos

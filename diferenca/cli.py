"""A linha de comando.

    python -m diferenca a.txt b.txt              o diff unificado
    python -m diferenca a.txt b.txt -U0          sem contexto
    python -m diferenca a.txt b.txt --palavras   marcando o que mudou na linha
    python -m diferenca aplicar a.txt mudanca.patch
    python -m diferenca reverter b.txt mudanca.patch
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .aplicar import ErroDePatch, aplicar, reverter
from .myers import Operacao
from .palavras import marcar, parecidas
from .unificado import CONTEXTO_PADRAO, separar, unificado

#: Abaixo desta semelhança, mostrar palavra a palavra atrapalha mais que ajuda.
SEMELHANCA_MINIMA = 0.4


def _ler(caminho: str) -> str:
    return Path(caminho).read_text(encoding="utf-8")


def comando_diff(argumentos) -> int:
    antigo = _ler(argumentos.antigo)
    novo = _ler(argumentos.novo)

    saida = unificado(
        antigo,
        novo,
        caminho_antigo=f"a/{Path(argumentos.antigo).name}",
        caminho_novo=f"b/{Path(argumentos.novo).name}",
        contexto=argumentos.contexto,
        com_secao=not argumentos.sem_secao,
    )

    if not saida:
        # Silêncio e código zero é o que o `diff` faz, e o que um script que
        # chama isto espera.
        return 0

    if argumentos.palavras:
        saida = _com_palavras(saida)

    sys.stdout.write(saida)

    return 1


def _com_palavras(patch: str) -> str:
    """Marca palavra a palavra os pares de linha trocada dentro de cada bloco.

    Dentro de um bloco de mudança, as remoções vêm todas antes das inserções —
    é o que toda ferramenta de diff faz. O emparelhamento aqui é **por
    posição**: a primeira removida com a primeira inserida, e assim por diante.

    É um palpite, e só se aplica quando os dois lados têm o mesmo número de
    linhas e o par se parece o bastante. Com contagens diferentes não há
    correspondência óbvia, e marcar palavras de linhas que não têm nada a ver
    uma com a outra é pior do que não marcar nada.
    """
    linhas = patch.split("\n")
    saida: list[str] = []
    i = 0

    def e_conteudo(linha: str, sinal: str) -> bool:
        return linha.startswith(sinal) and not linha.startswith(sinal * 3)

    while i < len(linhas):
        if not e_conteudo(linhas[i], "-"):
            saida.append(linhas[i])
            i += 1
            continue

        removidas = []

        while i < len(linhas) and e_conteudo(linhas[i], "-"):
            removidas.append(linhas[i][1:])
            i += 1

        inseridas = []

        while i < len(linhas) and e_conteudo(linhas[i], "+"):
            inseridas.append(linhas[i][1:])
            i += 1

        if len(removidas) == len(inseridas) and removidas:
            pares = [
                marcar(velha, nova) if parecidas(velha, nova) >= SEMELHANCA_MINIMA else (velha, nova)
                for velha, nova in zip(removidas, inseridas)
            ]

            saida.extend("-" + par[0] for par in pares)
            saida.extend("+" + par[1] for par in pares)
        else:
            saida.extend("-" + linha for linha in removidas)
            saida.extend("+" + linha for linha in inseridas)

    return "\n".join(saida)


def comando_aplicar(argumentos) -> int:
    try:
        resultado = aplicar(_ler(argumentos.arquivo), _ler(argumentos.patch))
    except ErroDePatch as erro:
        print(f"não deu para aplicar: {erro}", file=sys.stderr)

        return 1

    if argumentos.no_lugar:
        Path(argumentos.arquivo).write_text(resultado, encoding="utf-8")
        print(f"{argumentos.arquivo} atualizado.")
    else:
        sys.stdout.write(resultado)

    return 0


def comando_reverter(argumentos) -> int:
    try:
        resultado = reverter(_ler(argumentos.arquivo), _ler(argumentos.patch))
    except ErroDePatch as erro:
        print(f"não deu para reverter: {erro}", file=sys.stderr)

        return 1

    if argumentos.no_lugar:
        Path(argumentos.arquivo).write_text(resultado, encoding="utf-8")
        print(f"{argumentos.arquivo} revertido.")
    else:
        sys.stdout.write(resultado)

    return 0


def comando_contar(argumentos) -> int:
    from .myers import comparar

    antigas, _ = separar(_ler(argumentos.antigo))
    novas, _ = separar(_ler(argumentos.novo))
    edicoes = comparar(antigas, novas)

    inseridas = sum(1 for e in edicoes if e.operacao is Operacao.INSERIR)
    removidas = sum(1 for e in edicoes if e.operacao is Operacao.REMOVER)

    print(f" {len(antigas)} linha(s) antes, {len(novas)} depois")
    print(f" {inseridas} inserida(s), {removidas} removida(s)")
    print(f" distância de edição: {inseridas + removidas}")

    return 0


def principal(argumentos=None) -> int:
    analisador = argparse.ArgumentParser(
        prog="diferenca",
        description="Diff unificado do zero, pelo algoritmo de Myers.",
    )

    subcomandos = analisador.add_subparsers(dest="comando")

    diff = subcomandos.add_parser("diff", help="o diff unificado entre dois arquivos")
    diff.add_argument("antigo")
    diff.add_argument("novo")
    diff.add_argument("-U", "--contexto", type=int, default=CONTEXTO_PADRAO)
    diff.add_argument("--palavras", action="store_true", help="marcar o que mudou dentro da linha")
    diff.add_argument("--sem-secao", action="store_true", help="não escrever a declaração após o @@")
    diff.set_defaults(funcao=comando_diff)

    aplica = subcomandos.add_parser("aplicar", help="aplicar um patch a um arquivo")
    aplica.add_argument("arquivo")
    aplica.add_argument("patch")
    aplica.add_argument("--no-lugar", action="store_true", help="escrever por cima do arquivo")
    aplica.set_defaults(funcao=comando_aplicar)

    reverte = subcomandos.add_parser("reverter", help="desfazer um patch")
    reverte.add_argument("arquivo")
    reverte.add_argument("patch")
    reverte.add_argument("--no-lugar", action="store_true")
    reverte.set_defaults(funcao=comando_reverter)

    conta = subcomandos.add_parser("contar", help="quantas linhas mudaram")
    conta.add_argument("antigo")
    conta.add_argument("novo")
    conta.set_defaults(funcao=comando_contar)

    analisado = analisador.parse_args(argumentos)

    if analisado.comando is None:
        analisador.print_help()

        return 1

    try:
        return analisado.funcao(analisado)
    except FileNotFoundError as erro:
        print(f"não achei o arquivo: {erro.filename}", file=sys.stderr)

        return 2
    except ValueError as erro:
        print(erro, file=sys.stderr)

        return 2

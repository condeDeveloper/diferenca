"""diferenca — diff unificado do zero, pelo algoritmo de Myers.

Sem dependência nenhuma. A saída é a mesma do `git diff`, byte a byte.
"""

from .aplicar import ErroDePatch, TrechoLido, aplicar, ler, reverter
from .myers import Edicao, Operacao, blocos_iguais, comparar, distancia, remocoes_antes
from .palavras import diferenca_de_palavras, marcar, parecidas, separar_palavras
from .unificado import (
    CONTEXTO_PADRAO,
    SEM_QUEBRA,
    Trecho,
    secao,
    separar,
    trechos,
    unificado,
)

__all__ = [
    "CONTEXTO_PADRAO",
    "Edicao",
    "ErroDePatch",
    "Operacao",
    "SEM_QUEBRA",
    "Trecho",
    "TrechoLido",
    "aplicar",
    "blocos_iguais",
    "comparar",
    "diferenca_de_palavras",
    "distancia",
    "ler",
    "marcar",
    "parecidas",
    "remocoes_antes",
    "reverter",
    "secao",
    "separar",
    "separar_palavras",
    "trechos",
    "unificado",
]

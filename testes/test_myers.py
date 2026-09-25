"""O algoritmo, contra uma conta que não é a dele.

O oráculo aqui é matemático, não uma biblioteca: a maior subsequência comum
determina sozinha a distância mínima de edição, por ``D = (N − L) + (M − L)``.
Calcular L por programação dinâmica — lenta, quadrática e obviamente correta —
e exigir que Myers dê o mesmo D é uma prova de minimalidade, não uma
comparação de gosto.

O segundo oráculo é a própria definição: aplicar o roteiro de edição a um lado
tem de dar exatamente o outro. Um roteiro pode ter a contagem certa e o
conteúdo trocado — foi assim que o primeiro defeito deste projeto apareceu.
"""

from __future__ import annotations

import difflib
import random
import unittest

from diferenca.myers import (
    Edicao,
    Operacao,
    blocos_iguais,
    comparar,
    distancia,
    remocoes_antes,
)


def maior_subsequencia_comum(a, b) -> int:
    """O comprimento da maior subsequência comum, por força bruta.

    É O(N·M) em tempo e memória — exatamente o que Myers existe para evitar.
    Por isso serve de juiz: é a conta ingênua, escrita de outro jeito, e não
    compartilha nenhuma linha de código com o que ela julga.
    """
    n, m = len(a), len(b)
    tabela = [[0] * (m + 1) for _ in range(n + 1)]

    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            if a[i] == b[j]:
                tabela[i][j] = tabela[i + 1][j + 1] + 1
            else:
                tabela[i][j] = max(tabela[i + 1][j], tabela[i][j + 1])

    return tabela[0][0]


def reconstruir(edicoes):
    """Os dois lados, remontados a partir do roteiro."""
    a = [e.linha for e in edicoes if e.operacao is not Operacao.INSERIR]
    b = [e.linha for e in edicoes if e.operacao is not Operacao.REMOVER]

    return a, b


class TestOExemploDoArtigo(unittest.TestCase):
    """O exemplo que Myers usa no artigo de 1986."""

    def test_abcabba_para_cbabac(self):
        a = list("ABCABBA")
        b = list("CBABAC")

        # O artigo diz que o menor roteiro tem 5 edições.
        self.assertEqual(distancia(a, b), 5)

    def test_e_o_roteiro_reconstroi_os_dois_lados(self):
        a = list("ABCABBA")
        b = list("CBABAC")

        remontado_a, remontado_b = reconstruir(comparar(a, b))

        self.assertEqual(remontado_a, a)
        self.assertEqual(remontado_b, b)


class TestMinimalidade(unittest.TestCase):
    def test_bate_com_a_subsequencia_comum_em_milhares_de_casos(self):
        for alfabeto, tamanho, quantos in (("ab", 14, 1500), ("abcd", 10, 2000), ("abcdefgh", 18, 1000)):
            sorteio = random.Random(f"{alfabeto}{tamanho}")

            for _ in range(quantos):
                a = [sorteio.choice(alfabeto) for _ in range(sorteio.randint(0, tamanho))]
                b = [sorteio.choice(alfabeto) for _ in range(sorteio.randint(0, tamanho))]

                comum = maior_subsequencia_comum(a, b)
                esperado = (len(a) - comum) + (len(b) - comum)

                self.assertEqual(
                    distancia(a, b),
                    esperado,
                    f"a={''.join(a)!r} b={''.join(b)!r}",
                )

    def test_o_roteiro_sempre_reconstroi_os_dois_lados(self):
        sorteio = random.Random(99)

        for _ in range(3000):
            a = [sorteio.choice("abcd") for _ in range(sorteio.randint(0, 12))]
            b = [sorteio.choice("abcd") for _ in range(sorteio.randint(0, 12))]

            remontado_a, remontado_b = reconstruir(comparar(a, b))

            self.assertEqual(remontado_a, a)
            self.assertEqual(remontado_b, b)

    def test_lados_de_tamanhos_muito_diferentes(self):
        # Foi aqui que o primeiro defeito apareceu: o vetor das frentes de onda
        # estava dimensionado pelo intervalo das diagonais, que é menor que o
        # dos índices realmente consultados. Só estoura com lados desiguais.
        for n, m in ((0, 40), (40, 0), (1, 50), (50, 1), (3, 60), (60, 3)):
            with self.subTest(n=n, m=m):
                a = [f"a{i}" for i in range(n)]
                b = [f"b{i}" for i in range(m)]

                self.assertEqual(distancia(a, b), n + m)


class TestCasosSimples(unittest.TestCase):
    def test_iguais_nao_tem_edicao(self):
        a = ["um", "dois", "tres"]

        self.assertEqual(distancia(a, a), 0)
        self.assertTrue(all(e.operacao is Operacao.IGUAL for e in comparar(a, a)))

    def test_dois_vazios(self):
        self.assertEqual(comparar([], []), [])
        self.assertEqual(distancia([], []), 0)

    def test_tudo_inserido(self):
        edicoes = comparar([], ["a", "b"])

        self.assertEqual([e.operacao for e in edicoes], [Operacao.INSERIR] * 2)

    def test_tudo_removido(self):
        edicoes = comparar(["a", "b"], [])

        self.assertEqual([e.operacao for e in edicoes], [Operacao.REMOVER] * 2)

    def test_as_posicoes_vem_preenchidas(self):
        edicoes = comparar(["a", "b"], ["a", "c"])
        por_operacao = {e.operacao: e for e in edicoes}

        self.assertEqual(por_operacao[Operacao.IGUAL].antiga, 0)
        self.assertEqual(por_operacao[Operacao.IGUAL].nova, 0)
        self.assertIsNone(por_operacao[Operacao.REMOVER].nova)
        self.assertIsNone(por_operacao[Operacao.INSERIR].antiga)

    def test_a_edicao_se_escreve_como_no_diff(self):
        self.assertEqual(str(Edicao(Operacao.REMOVER, "x", 0, None)), "-x")
        self.assertEqual(str(Edicao(Operacao.INSERIR, "x", None, 0)), "+x")
        self.assertEqual(str(Edicao(Operacao.IGUAL, "x", 0, 0)), " x")


class TestOrdemDoBloco(unittest.TestCase):
    def test_remocoes_vem_antes_das_insercoes(self):
        # Todos os caminhos de custo mínimo servem, e o algoritmo não tem
        # motivo para preferir um. Mas toda ferramenta mostra o bloco com as
        # remoções primeiro, e quem lê conta com isso.
        for edicao_a, edicao_b in (("abc", "xyz"), ("abcd", "wxyz"), ("aXbY", "aPbQ")):
            with self.subTest(a=edicao_a, b=edicao_b):
                edicoes = comparar(list(edicao_a), list(edicao_b))
                bloco: list[Operacao] = []

                for edicao in edicoes:
                    if edicao.operacao is Operacao.IGUAL:
                        bloco.clear()
                        continue

                    if bloco and bloco[-1] is Operacao.INSERIR:
                        self.assertIsNot(
                            edicao.operacao,
                            Operacao.REMOVER,
                            "uma remoção apareceu depois de uma inserção no mesmo bloco",
                        )

                    bloco.append(edicao.operacao)

    def test_reordenar_nao_muda_o_que_cada_lado_reconstroi(self):
        sorteio = random.Random(5)

        for _ in range(500):
            a = [sorteio.choice("abc") for _ in range(sorteio.randint(0, 10))]
            b = [sorteio.choice("abc") for _ in range(sorteio.randint(0, 10))]

            cru = comparar(a, b)
            ordenado = remocoes_antes(cru)

            self.assertEqual(reconstruir(cru), reconstruir(ordenado))


class TestBlocosIguais(unittest.TestCase):
    def test_nunca_acha_menos_em_comum_que_o_difflib(self):
        """O `difflib` da biblioteca padrão **não** é minimal.

        Esta era para ser uma comparação de igualdade, e ela falhou — e quem
        estava errado era a expectativa, não o código. O `SequenceMatcher` não
        usa Myers: ele é um casamento guloso de maiores blocos, no estilo
        Ratcliff/Obershelp, e não garante a maior subsequência comum.

        Em ``ababddd`` contra ``dbbbccc`` ele acha 2 linhas em comum onde
        existem 3. Como o roteiro daqui é comprovadamente mínimo (ver
        `TestMinimalidade`), o que vale é a desigualdade: nunca menos que o
        difflib, e às vezes mais.
        """
        sorteio = random.Random(31)
        ganhou_alguma_vez = False

        for _ in range(400):
            a = [sorteio.choice("abcd") for _ in range(sorteio.randint(0, 12))]
            b = [sorteio.choice("abcd") for _ in range(sorteio.randint(0, 12))]

            meus = sum(tamanho for _, _, tamanho in blocos_iguais(a, b))
            deles = sum(
                bloco.size for bloco in difflib.SequenceMatcher(None, a, b).get_matching_blocks()
            )

            self.assertGreaterEqual(meus, deles, f"a={a} b={b}")
            self.assertEqual(meus, maior_subsequencia_comum(a, b), f"a={a} b={b}")

            if meus > deles:
                ganhou_alguma_vez = True

        self.assertTrue(ganhou_alguma_vez, "se nunca ganha, o teste não está provando nada")

    def test_o_caso_concreto_em_que_o_difflib_perde(self):
        a = list("dbbbccc")
        b = list("cababdddcbd")

        meus = sum(tamanho for _, _, tamanho in blocos_iguais(a, b))
        deles = sum(
            bloco.size for bloco in difflib.SequenceMatcher(None, a, b).get_matching_blocks()
        )

        self.assertEqual(maior_subsequencia_comum(a, b), 3)
        self.assertEqual(meus, 3)
        self.assertEqual(deles, 2)

    def test_os_blocos_apontam_para_conteudo_igual(self):
        a = list("xabcy")
        b = list("zabcw")

        for i, j, tamanho in blocos_iguais(a, b):
            self.assertEqual(a[i : i + tamanho], b[j : j + tamanho])

    def test_sem_nada_em_comum_nao_ha_bloco(self):
        self.assertEqual(blocos_iguais(list("abc"), list("xyz")), [])


class TestDesempenho(unittest.TestCase):
    def test_arquivo_grande_com_diferenca_pequena_e_rapido(self):
        # O argumento inteiro a favor de Myers: o custo acompanha o tamanho da
        # *diferença*, não o dos arquivos. Dez mil linhas com três mudanças
        # resolvem na hora; a tabela quadrática pediria cem milhões de células.
        a = [f"linha {i}" for i in range(10_000)]
        b = list(a)

        b[100] = "mudou aqui"
        b[5_000] = "e aqui"

        del b[9_000]

        self.assertEqual(distancia(a, b), 5)


if __name__ == "__main__":
    unittest.main()

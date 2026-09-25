"""Aplicar e reverter — a metade que não deixa a outra mentir."""

from __future__ import annotations

import random
import unittest

from diferenca.aplicar import ErroDePatch, aplicar, ler, reverter
from diferenca.unificado import unificado


class TestLerOPatch(unittest.TestCase):
    def test_le_o_cabecalho_com_e_sem_virgula(self):
        patch = "@@ -5 +5,2 @@\n-a\n+a\n+b\n"
        trecho = ler(patch)[0]

        self.assertEqual(trecho.inicio_antigo, 5)
        self.assertEqual(trecho.quantas_antigas, 1)
        self.assertEqual(trecho.inicio_novo, 5)
        self.assertEqual(trecho.quantas_novas, 2)

    def test_guarda_a_secao_do_cabecalho(self):
        trecho = ler("@@ -1 +1 @@ def f():\n-a\n+b\n")[0]

        self.assertEqual(trecho.secao, "def f():")

    def test_ignora_o_cabecalho_do_git(self):
        # Um patch de verdade quase nunca chega só com os `@@`.
        patch = (
            "diff --git a/x.txt b/x.txt\n"
            "index 1234567..89abcde 100644\n"
            "--- a/x.txt\n"
            "+++ b/x.txt\n"
            "@@ -1 +1 @@\n"
            "-a\n"
            "+b\n"
        )

        self.assertEqual(len(ler(patch)), 1)

    def test_patch_sem_trecho_nenhum_e_recusado(self):
        with self.assertRaises(ErroDePatch):
            ler("isto não é um patch\n")

    def test_contagem_que_nao_bate_com_o_conteudo_e_recusada(self):
        # Confiar na contagem faz o resto do arquivo escorregar em silêncio.
        with self.assertRaises(ErroDePatch) as capturado:
            ler("@@ -1,5 +1,5 @@\n a\n-b\n+c\n")

        self.assertIn("mas traz", str(capturado.exception))

    def test_linha_de_contexto_sem_o_espaco_ainda_e_lida(self):
        # Muito cliente de e-mail come o espaço da linha de contexto vazia.
        # Tratar isso como fim do trecho perderia conteúdo sem avisar.
        trechos = ler("@@ -1,3 +1,3 @@\n a\n\n-b\n+c\n")

        self.assertEqual(trechos[0].quantas_antigas, 3)


class TestAplicar(unittest.TestCase):
    def test_o_caso_basico(self):
        antigo = "um\ndois\ntres\n"
        novo = "um\nDOIS\ntres\n"

        self.assertEqual(aplicar(antigo, unificado(antigo, novo)), novo)

    def test_varios_trechos(self):
        antigo = "".join(f"l{i}\n" for i in range(40))
        novo = antigo.replace("l2\n", "X\n").replace("l30\n", "Y\n")

        self.assertEqual(aplicar(antigo, unificado(antigo, novo)), novo)

    def test_criando_um_arquivo(self):
        self.assertEqual(aplicar("", unificado("", "a\nb\n")), "a\nb\n")

    def test_esvaziando_um_arquivo(self):
        self.assertEqual(aplicar("a\nb\n", unificado("a\nb\n", "")), "")

    def test_contexto_que_nao_bate_e_recusado(self):
        # É a diferença entre um aplicador e um gerador de estrago.
        patch = unificado("a\nb\nc\n", "a\nX\nc\n")

        with self.assertRaises(ErroDePatch) as capturado:
            aplicar("a\nOUTRO\nc\n", patch)

        self.assertIn("não bate", str(capturado.exception))

    def test_trecho_alem_do_fim_do_arquivo_e_recusado(self):
        with self.assertRaises(ErroDePatch):
            aplicar("a\n", "@@ -50 +50 @@\n-x\n+y\n")

    def test_trechos_fora_de_ordem_sao_recusados(self):
        patch = "@@ -5 +5 @@\n-l4\n+X\n@@ -2 +2 @@\n-l1\n+Y\n"

        with self.assertRaises(ErroDePatch) as capturado:
            aplicar("".join(f"l{i}\n" for i in range(9)), patch)

        self.assertIn("volta para trás", str(capturado.exception))


class TestQuebraDeLinhaFinal(unittest.TestCase):
    def test_o_arquivo_sem_quebra_continua_sem(self):
        antigo = "a\nb"
        novo = "a\nX"

        self.assertEqual(aplicar(antigo, unificado(antigo, novo)), novo)

    def test_ganhando_a_quebra(self):
        self.assertEqual(aplicar("a\nb", unificado("a\nb", "a\nb\n")), "a\nb\n")

    def test_perdendo_a_quebra(self):
        self.assertEqual(aplicar("a\nb\n", unificado("a\nb\n", "a\nb")), "a\nb")

    def test_a_marca_do_lado_antigo_nao_muda_o_resultado(self):
        # A marca depois de um `-` descreve o arquivo que está sendo
        # substituído, e não diz nada sobre o que vai sair. Tratar as duas
        # iguais erra justamente nos dois sentidos em que o caso importa.
        antigo = "a\nb"
        novo = "a\nb\nc\n"
        patch = unificado(antigo, novo)

        self.assertIn("\\ No newline", patch)
        self.assertEqual(aplicar(antigo, patch), novo)

    def test_cauda_inalterada_mantem_a_quebra_do_original(self):
        antigo = "".join(f"l{i}\n" for i in range(20))[:-1]
        novo = antigo.replace("l1\n", "X\n")

        self.assertEqual(aplicar(antigo, unificado(antigo, novo)), novo)


class TestReverter(unittest.TestCase):
    def test_desfaz_uma_mudanca(self):
        antigo = "um\ndois\ntres\n"
        novo = "um\nDOIS\ntres\n"

        self.assertEqual(reverter(novo, unificado(antigo, novo)), antigo)

    def test_desfaz_criacao(self):
        self.assertEqual(reverter("a\nb\n", unificado("", "a\nb\n")), "")

    def test_desfaz_sem_a_quebra_final(self):
        antigo = "a\nb"
        novo = "a\nX"

        self.assertEqual(reverter(novo, unificado(antigo, novo)), antigo)

    def test_reverter_o_reverso_volta_ao_novo(self):
        antigo = "".join(f"l{i}\n" for i in range(15))
        novo = antigo.replace("l7\n", "SETE\n")
        patch = unificado(antigo, novo)

        self.assertEqual(aplicar(reverter(novo, patch), patch), novo)


class TestIdaEVolta(unittest.TestCase):
    def test_oito_mil_pares_sorteados(self):
        """A propriedade que define o projeto.

        Gerar o diff e aplicá-lo tem de devolver **exatamente** o outro
        arquivo, e revertê-lo tem de devolver o primeiro. Não é comparação de
        texto: é a definição de estar certo.

        A quebra de linha final é sorteada de propósito nos dois lados — foi aí
        que moraram três dos quatro defeitos deste projeto.
        """
        sorteio = random.Random(20260925)
        conferidos = 0

        for _ in range(8000):
            base = [f"linha {i}" for i in range(sorteio.randint(0, 20))]
            novo = list(base)

            for _ in range(sorteio.randint(0, 6)):
                if not novo or sorteio.random() < 0.4:
                    novo.insert(sorteio.randint(0, len(novo)), f"novo {sorteio.randint(0, 99)}")
                elif sorteio.random() < 0.5:
                    novo.pop(sorteio.randrange(len(novo)))
                else:
                    novo[sorteio.randrange(len(novo))] = f"mudado {sorteio.randint(0, 99)}"

            antigo = "\n".join(base) + ("\n" if base and sorteio.random() < 0.85 else "")
            depois = "\n".join(novo) + ("\n" if novo and sorteio.random() < 0.85 else "")

            patch = unificado(antigo, depois)

            if not patch:
                self.assertEqual(antigo, depois, "diff vazio entre arquivos diferentes")
                continue

            self.assertEqual(aplicar(antigo, patch), depois, f"antigo={antigo!r} novo={depois!r}")
            self.assertEqual(reverter(depois, patch), antigo, f"antigo={antigo!r} novo={depois!r}")

            conferidos += 1

        self.assertGreater(conferidos, 7000, "quase todos os pares têm de ter diferença")


if __name__ == "__main__":
    unittest.main()

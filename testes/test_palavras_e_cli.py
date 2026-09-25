"""Diferença dentro da linha, e a linha de comando rodada de verdade."""

from __future__ import annotations

import contextlib
import io
import shutil
import tempfile
import unittest
from pathlib import Path

from diferenca.cli import principal
from diferenca.myers import Operacao
from diferenca.palavras import (
    diferenca_de_palavras,
    marcar,
    parecidas,
    separar_palavras,
)


class TestSepararPalavras(unittest.TestCase):
    def test_palavra_espaco_e_pontuacao_sao_itens_separados(self):
        # Partir em caracteres dá resultado correto e ilegível; partir só por
        # espaço faz `frete` e `frete;` parecerem coisas sem relação.
        self.assertEqual(separar_palavras("a = b;"), ["a", " ", "=", " ", "b", ";"])

    def test_junta_espacos_seguidos(self):
        self.assertEqual(separar_palavras("a    b"), ["a", "    ", "b"])

    def test_preserva_a_indentacao(self):
        self.assertEqual(separar_palavras("    x")[0], "    ")

    def test_acentos_ficam_na_mesma_palavra(self):
        self.assertEqual(separar_palavras("preço total"), ["preço", " ", "total"])

    def test_linha_vazia(self):
        self.assertEqual(separar_palavras(""), [])

    def test_remonta_a_linha_original(self):
        for linha in ("a = b + c;", "    return x", "def f(a, b):", "", "   "):
            with self.subTest(linha=linha):
                self.assertEqual("".join(separar_palavras(linha)), linha)


class TestDiferencaDePalavras(unittest.TestCase):
    def test_junta_trechos_seguidos_da_mesma_operacao(self):
        # Sem juntar sai uma tupla por palavra e por espaço, o que é ruído.
        partes = diferenca_de_palavras("a b c", "a b c d e")
        inseridos = [texto for operacao, texto in partes if operacao is Operacao.INSERIR]

        self.assertEqual(inseridos, [" d e"])

    def test_linhas_iguais_nao_tem_mudanca(self):
        partes = diferenca_de_palavras("igual", "igual")

        self.assertTrue(all(operacao is Operacao.IGUAL for operacao, _ in partes))

    def test_remonta_os_dois_lados(self):
        antiga, nova = "soma = a + b", "soma = a + b + c"
        partes = diferenca_de_palavras(antiga, nova)

        remontada_antiga = "".join(t for o, t in partes if o is not Operacao.INSERIR)
        remontada_nova = "".join(t for o, t in partes if o is not Operacao.REMOVER)

        self.assertEqual(remontada_antiga, antiga)
        self.assertEqual(remontada_nova, nova)


class TestMarcar(unittest.TestCase):
    def test_marca_so_o_que_mudou(self):
        velha, nova = marcar("total = preco * qtd", "total = preco * qtd + imposto")

        self.assertEqual(velha, "total = preco * qtd")
        self.assertEqual(nova, "total = preco * qtd{+ + imposto+}")

    def test_marca_a_remocao_no_lado_antigo(self):
        velha, nova = marcar("a + b + c", "a + c")

        self.assertIn("[-", velha)
        self.assertNotIn("[-", nova)

    def test_as_marcas_dao_para_trocar(self):
        velha, _ = marcar("a b", "a", abre="<<", fecha=">>")

        self.assertIn("<<", velha)


class TestParecidas(unittest.TestCase):
    def test_iguais_dao_um(self):
        self.assertEqual(parecidas("a b c", "a b c"), 1.0)

    def test_sem_nada_em_comum_da_zero(self):
        self.assertEqual(parecidas("xxx", "yyy"), 0.0)

    def test_duas_vazias_dao_um(self):
        self.assertEqual(parecidas("", ""), 1.0)

    def test_fica_entre_zero_e_um(self):
        for antiga, nova in (("a b c d", "a b x y"), ("", "a"), ("a", ""), ("abc", "abd")):
            with self.subTest(antiga=antiga, nova=nova):
                self.assertGreaterEqual(parecidas(antiga, nova), 0.0)
                self.assertLessEqual(parecidas(antiga, nova), 1.0)


def rodar(*argumentos):
    """Roda a linha de comando e devolve código, saída e erro."""
    saida, erro = io.StringIO(), io.StringIO()

    with contextlib.redirect_stdout(saida), contextlib.redirect_stderr(erro):
        codigo = principal(list(argumentos))

    return codigo, saida.getvalue(), erro.getvalue()


class TestLinhaDeComando(unittest.TestCase):
    def setUp(self):
        self.pasta = Path(tempfile.mkdtemp(prefix="diferenca-cli-"))
        self.a = self.pasta / "a.txt"
        self.b = self.pasta / "b.txt"

        self.a.write_text("um\ndois\ntres\n", encoding="utf-8")
        self.b.write_text("um\nDOIS\ntres\n", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.pasta, ignore_errors=True)

    def test_diff_sai_com_um_quando_ha_diferenca(self):
        # É o que o `diff` faz, e o que um script que chama isto espera.
        codigo, saida, _ = rodar("diff", str(self.a), str(self.b))

        self.assertEqual(codigo, 1)
        self.assertIn("-dois", saida)
        self.assertIn("+DOIS", saida)

    def test_diff_sai_com_zero_e_calado_quando_sao_iguais(self):
        codigo, saida, _ = rodar("diff", str(self.a), str(self.a))

        self.assertEqual(codigo, 0)
        self.assertEqual(saida, "")

    def test_contexto_pela_opcao(self):
        longo = self.pasta / "longo.txt"
        outro = self.pasta / "outro.txt"

        longo.write_text("".join(f"l{i}\n" for i in range(20)), encoding="utf-8")
        outro.write_text(longo.read_text(encoding="utf-8").replace("l10\n", "X\n"), encoding="utf-8")

        _, com_zero, _ = rodar("diff", "-U0", str(longo), str(outro))
        _, com_cinco, _ = rodar("diff", "-U5", str(longo), str(outro))

        self.assertLess(len(com_zero.split("\n")), len(com_cinco.split("\n")))

    def test_palavras_marca_dentro_da_linha(self):
        a = self.pasta / "p1.txt"
        b = self.pasta / "p2.txt"

        a.write_text("total = preco * qtd\n", encoding="utf-8")
        b.write_text("total = preco * qtd + imposto\n", encoding="utf-8")

        _, saida, _ = rodar("diff", "--palavras", str(a), str(b))

        self.assertIn("{+", saida)

    def test_palavras_nao_marca_linhas_sem_relacao(self):
        # Marcar palavra a palavra duas linhas que não têm nada em comum é
        # pior do que não marcar nada.
        a = self.pasta / "d1.txt"
        b = self.pasta / "d2.txt"

        a.write_text("aaaa bbbb cccc\n", encoding="utf-8")
        b.write_text("zzzz yyyy xxxx\n", encoding="utf-8")

        _, saida, _ = rodar("diff", "--palavras", str(a), str(b))

        self.assertNotIn("{+", saida)

    def test_aplicar_escreve_no_lugar(self):
        patch = self.pasta / "mudanca.patch"
        _, texto, _ = rodar("diff", str(self.a), str(self.b))

        patch.write_text(texto, encoding="utf-8")

        codigo, _, _ = rodar("aplicar", "--no-lugar", str(self.a), str(patch))

        self.assertEqual(codigo, 0)
        self.assertEqual(self.a.read_text(encoding="utf-8"), self.b.read_text(encoding="utf-8"))

    def test_reverter_desfaz(self):
        patch = self.pasta / "mudanca.patch"
        _, texto, _ = rodar("diff", str(self.a), str(self.b))

        patch.write_text(texto, encoding="utf-8")

        codigo, saida, _ = rodar("reverter", str(self.b), str(patch))

        self.assertEqual(codigo, 0)
        self.assertEqual(saida, self.a.read_text(encoding="utf-8"))

    def test_patch_que_nao_bate_sai_com_erro_explicado(self):
        patch = self.pasta / "ruim.patch"

        patch.write_text("@@ -1 +1 @@\n-nao existe\n+outra\n", encoding="utf-8")

        codigo, _, erro = rodar("aplicar", str(self.a), str(patch))

        self.assertEqual(codigo, 1)
        self.assertIn("não bate", erro)

    def test_contar(self):
        codigo, saida, _ = rodar("contar", str(self.a), str(self.b))

        self.assertEqual(codigo, 0)
        self.assertIn("1 inserida(s), 1 removida(s)", saida)
        self.assertIn("distância de edição: 2", saida)

    def test_arquivo_que_nao_existe(self):
        codigo, _, erro = rodar("diff", str(self.a), str(self.pasta / "nao-existe.txt"))

        self.assertEqual(codigo, 2)
        self.assertIn("não achei o arquivo", erro)

    def test_sem_comando_mostra_a_ajuda(self):
        codigo, saida, _ = rodar()

        self.assertEqual(codigo, 1)
        self.assertIn("Myers", saida)

    def test_comando_desconhecido(self):
        with self.assertRaises(SystemExit):
            rodar("transcodificar", "a", "b")


if __name__ == "__main__":
    unittest.main()

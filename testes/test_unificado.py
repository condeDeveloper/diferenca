"""O formato: cabeçalhos, agrupamento e a quebra de linha do fim."""

from __future__ import annotations

import unittest

from diferenca.myers import Operacao, comparar
from diferenca.unificado import (
    CONTEXTO_PADRAO,
    SEM_QUEBRA,
    secao,
    separar,
    trechos,
    unificado,
)


class TestSeparar(unittest.TestCase):
    def test_guarda_se_termina_com_quebra(self):
        # `splitlines()` sozinho perde essa informação — e ela muda a saída.
        self.assertEqual(separar("a\nb\n"), (["a", "b"], True))
        self.assertEqual(separar("a\nb"), (["a", "b"], False))

    def test_texto_vazio_nao_tem_linha_nenhuma(self):
        self.assertEqual(separar(""), ([], True))

    def test_uma_linha_vazia_e_diferente_de_nenhuma_linha(self):
        # Um arquivo com um "\n" só tem uma linha, e ela é vazia.
        self.assertEqual(separar("\n"), ([""], True))

    def test_linhas_vazias_no_meio_sobrevivem(self):
        self.assertEqual(separar("a\n\nb\n"), (["a", "", "b"], True))


class TestCabecalhoDoTrecho(unittest.TestCase):
    def monta(self, antigo, novo, contexto=CONTEXTO_PADRAO):
        return trechos(comparar(antigo, novo), contexto)

    def test_uma_linha_nao_leva_virgula(self):
        antigo = [f"l{i}" for i in range(9)]
        novo = list(antigo)
        novo[4] = "X"

        trecho = self.monta(antigo, novo, contexto=0)[0]

        self.assertEqual(trecho.cabecalho(), "@@ -5 +5 @@")

    def test_varias_linhas_levam_virgula(self):
        trecho = self.monta(["a", "b", "c"], ["a", "X", "c"])[0]

        self.assertEqual(trecho.cabecalho(), "@@ -1,3 +1,3 @@")

    def test_lado_sem_nenhuma_linha_aponta_para_a_posicao(self):
        # Numa remoção pura não há linha nova para tirar o número; ele vem da
        # contagem do que já saiu. Com `-U0` é o único jeito de acertar.
        antigo = [f"l{i}" for i in range(9)]
        novo = [l for l in antigo if l != "l4"]

        trecho = self.monta(antigo, novo, contexto=0)[0]

        self.assertEqual(trecho.cabecalho(), "@@ -5 +4,0 @@")

    def test_arquivo_criado_comeca_em_zero(self):
        trecho = self.monta([], ["a", "b"])[0]

        self.assertEqual(trecho.cabecalho(), "@@ -0,0 +1,2 @@")

    def test_a_secao_entra_depois_do_segundo_arroba(self):
        trecho = self.monta(["a", "b", "c"], ["a", "X", "c"])[0]

        self.assertEqual(trecho.cabecalho("def f():"), "@@ -1,3 +1,3 @@ def f():")

    def test_secao_vazia_nao_deixa_espaco_sobrando(self):
        trecho = self.monta(["a", "b", "c"], ["a", "X", "c"])[0]

        self.assertFalse(trecho.cabecalho("").endswith(" "))


class TestAgrupamento(unittest.TestCase):
    def test_mudancas_longe_viram_trechos_separados(self):
        antigo = [f"l{i}" for i in range(40)]
        novo = list(antigo)
        novo[2] = "X"
        novo[30] = "Y"

        self.assertEqual(len(trechos(comparar(antigo, novo))), 2)

    def test_mudancas_perto_viram_um_trecho_so(self):
        # Com três de contexto, duas mudanças a quatro linhas de distância
        # compartilham linhas — emitir dois trechos as repetiria, e o `patch`
        # recusaria o resultado.
        antigo = [f"l{i}" for i in range(20)]
        novo = list(antigo)
        novo[5] = "X"
        novo[9] = "Y"

        self.assertEqual(len(trechos(comparar(antigo, novo))), 1)

    def test_a_fronteira_exata_do_agrupamento(self):
        antigo = [f"l{i}" for i in range(40)]

        def quantos(distancia):
            novo = list(antigo)
            novo[5] = "X"
            novo[5 + distancia] = "Y"

            return len(trechos(comparar(antigo, novo)))

        # Com contexto 3, sete linhas iguais entre as mudanças ainda encostam
        # os trechos; oito já os separa.
        self.assertEqual(quantos(7), 1)
        self.assertEqual(quantos(8), 2)

    def test_sem_mudanca_nao_ha_trecho(self):
        self.assertEqual(trechos(comparar(["a"], ["a"])), [])

    def test_contexto_negativo_e_recusado(self):
        with self.assertRaises(ValueError):
            trechos(comparar(["a"], ["b"]), contexto=-1)

    def test_contexto_maior_que_o_arquivo_nao_estoura(self):
        saida = unificado("a\nb\n", "a\nX\n", contexto=100)

        self.assertIn("@@ -1,2 +1,2 @@", saida)


class TestSecao(unittest.TestCase):
    def test_pega_a_declaracao_acima(self):
        linhas = ["def f():", "    a = 1", "    b = 2"]

        self.assertEqual(secao(linhas, 3), "def f():")

    def test_pula_o_corpo_indentado(self):
        linhas = ["class C:", "    def m(self):", "        x = 1"]

        # Só `class C:` começa na coluna zero com letra.
        self.assertEqual(secao(linhas, 3), "class C:")

    def test_no_comeco_do_arquivo_nao_ha_secao(self):
        self.assertEqual(secao(["def f():"], 0), "")

    def test_linha_em_branco_nao_conta(self):
        self.assertEqual(secao(["def f():", "", "    x = 1"], 3), "def f():")

    def test_aceita_sublinhado_e_cifrao(self):
        self.assertEqual(secao(["_privado():"], 1), "_privado():")
        self.assertEqual(secao(["$var = 1"], 1), "$var = 1")

    def test_tira_espaco_do_fim(self):
        self.assertEqual(secao(["def f():   "], 1), "def f():")


class TestQuebraDeLinhaFinal(unittest.TestCase):
    def test_a_marca_aparece_quando_falta_a_quebra(self):
        saida = unificado("a\nb", "a\nX")

        self.assertIn(SEM_QUEBRA, saida)

    def test_so_a_quebra_mudando_ja_e_uma_mudanca(self):
        # O conteúdo é idêntico; só a quebra do fim mudou. Um diff vazio aqui
        # mentiria, porque aplicá-lo não daria o arquivo novo.
        saida = unificado("a\nb", "a\nb\n")

        self.assertNotEqual(saida, "")
        self.assertIn("-b", saida)
        self.assertIn("+b", saida)
        self.assertIn(SEM_QUEBRA, saida)

    def test_a_marca_fica_no_lado_certo(self):
        # O antigo é que não tem quebra, então a marca vem depois do `-`.
        linhas = unificado("a\nb", "a\nb\n").split("\n")
        posicao = linhas.index(SEM_QUEBRA)

        self.assertEqual(linhas[posicao - 1], "-b")

    def test_duas_marcas_quando_faltam_nos_dois(self):
        saida = unificado("a\nb", "a\nX")

        self.assertEqual(saida.count(SEM_QUEBRA), 2)

    def test_uma_marca_so_quando_falta_nos_dois_e_a_linha_nao_mudou(self):
        saida = unificado("a\nb\nc", "a\nX\nc")

        self.assertEqual(saida.count(SEM_QUEBRA), 1)

    def test_a_ultima_linha_ganha_quebra_por_ter_ganhado_vizinha(self):
        # `b` era a última do antigo e não tinha quebra; no novo ela continua
        # igual mas ganhou uma linha depois — logo ganhou quebra, e não pode
        # sair como contexto.
        saida = unificado("a\nb", "a\nb\nc\n")

        self.assertIn("-b", saida)
        self.assertIn("+b", saida)


class TestSaidaCompleta(unittest.TestCase):
    def test_arquivos_iguais_dao_texto_vazio(self):
        self.assertEqual(unificado("a\nb\n", "a\nb\n"), "")

    def test_dois_vazios_dao_texto_vazio(self):
        self.assertEqual(unificado("", ""), "")

    def test_os_caminhos_entram_no_cabecalho(self):
        saida = unificado("a\n", "b\n", "a/velho.txt", "b/novo.txt")

        self.assertTrue(saida.startswith("--- a/velho.txt\n+++ b/novo.txt\n"))

    def test_sempre_termina_com_quebra(self):
        self.assertTrue(unificado("a\n", "b\n").endswith("\n"))

    def test_da_para_desligar_a_secao(self):
        antigo = "def f():\n" + "".join(f"    p{i}\n" for i in range(10))
        novo = antigo.replace("    p7\n", "    P7\n")

        com = unificado(antigo, novo)
        sem = unificado(antigo, novo, com_secao=False)

        self.assertIn("@@ def f():", com)
        self.assertNotIn("def f():", sem.split("\n")[2])

    def test_toda_linha_do_corpo_comeca_com_marca_valida(self):
        antigo = "".join(f"l{i}\n" for i in range(20))
        novo = antigo.replace("l5\n", "X\n").replace("l15\n", "")

        for linha in unificado(antigo, novo).split("\n")[2:]:
            if not linha:
                continue

            self.assertTrue(
                linha[0] in " +-@\\",
                f"linha inesperada no corpo do diff: {linha!r}",
            )


if __name__ == "__main__":
    unittest.main()

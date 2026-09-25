"""O oráculo: o `git diff` de verdade.

Um diff é fácil de acreditar que está certo, porque a saída *parece* boa. O
único juiz honesto é uma ferramenta que não é minha — e não uma biblioteca que
eu escolhi, mas a que o mundo inteiro usa para ler código.

Os testes rodam `git diff --no-index` de verdade e exigem a saída **byte a
byte**. Onde eles passam, não sobra espaço para "é equivalente": é igual.

A única bandeira passada ao git é `--no-indent-heuristic`. Ela desliga um
ajuste que o git faz *depois* do algoritmo, deslizando o trecho para alinhar
com linhas em branco e indentação — é escolha de apresentação entre diffs
igualmente mínimos, não parte de Myers. Está nos limites do README.
"""

from __future__ import annotations

import random
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from diferenca.aplicar import aplicar, reverter
from diferenca.unificado import unificado

TEM_GIT = shutil.which("git") is not None


def corpo(patch: str) -> str:
    """O patch sem as duas linhas de cabeçalho `---`/`+++`.

    O git escreve o caminho completo do arquivo temporário nelas; o que
    interessa comparar é o resto.
    """
    return "\n".join(patch.split("\n")[2:]).rstrip("\n")


@unittest.skipUnless(TEM_GIT, "o git não está instalado")
class TestContraOGit(unittest.TestCase):
    """Cada teste roda o git de verdade e compara."""

    @classmethod
    def setUpClass(cls):
        cls.pasta = Path(tempfile.mkdtemp(prefix="diferenca-"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.pasta, ignore_errors=True)

    def git_diff(self, antigo: str, novo: str, contexto: int = 3) -> str:
        a = self.pasta / "antigo.txt"
        b = self.pasta / "novo.txt"

        a.write_bytes(antigo.encode("utf-8"))
        b.write_bytes(novo.encode("utf-8"))

        resultado = subprocess.run(
            [
                # `core.autocrlf` fixo: no Windows ele reescreve as quebras de
                # linha e o teste passaria a medir a configuração da máquina
                # em vez do algoritmo.
                "git", "-c", "core.autocrlf=false",
                "diff", "--no-index", "--no-color", "--no-indent-heuristic",
                f"-U{contexto}", str(a), str(b),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        linhas = resultado.stdout.split("\n")
        comeco = next((i for i, l in enumerate(linhas) if l.startswith("--- ")), None)

        return "\n".join(linhas[comeco:]) if comeco is not None else ""

    def conferir(self, antigo: str, novo: str, contexto: int = 3):
        meu = unificado(antigo, novo, contexto=contexto)

        self.assertEqual(corpo(meu), corpo(self.git_diff(antigo, novo, contexto)))

        return meu

    def test_troca_no_meio(self):
        a = "um\ndois\ntres\nquatro\ncinco\nseis\nsete\noito\n"
        b = "um\ndois\nTRES\nquatro\ncinco\nseis\nsete\nOITO\nnove\n"

        self.conferir(a, b)

    def test_arquivo_criado_do_nada(self):
        # O cabeçalho de um arquivo criado começa em 0, não em 1.
        patch = self.conferir("", "um\ndois\n")

        self.assertIn("@@ -0,0 +1,2 @@", patch)

    def test_arquivo_esvaziado(self):
        self.conferir("um\ndois\n", "")

    def test_uma_linha_so_nao_leva_virgula(self):
        # `@@ -3 +3 @@`, e não `@@ -3,1 +3,1 @@`. Precisa de contexto zero:
        # com os três de sempre o trecho engole o arquivo inteiro e a contagem
        # deixa de ser 1.
        patch = self.conferir("a\nb\nc\nd\ne\n", "a\nb\nX\nd\ne\n", contexto=0)

        self.assertIn("@@ -3 +3 @@", patch)

    def test_dois_trechos_separados(self):
        a = "".join(f"linha {i}\n" for i in range(40))
        b = a.replace("linha 2\n", "MUDOU 2\n").replace("linha 30\n", "MUDOU 30\n")

        patch = self.conferir(a, b)

        self.assertEqual(patch.count("@@ -"), 2)

    def test_dois_trechos_que_se_encostam_viram_um(self):
        # Com três linhas de contexto, mudanças a menos de sete linhas de
        # distância compartilham contexto e precisam sair num trecho só.
        a = "".join(f"linha {i}\n" for i in range(20))
        b = a.replace("linha 5\n", "MUDOU 5\n").replace("linha 9\n", "MUDOU 9\n")

        patch = self.conferir(a, b)

        self.assertEqual(patch.count("@@ -"), 1)

    def test_sem_quebra_no_fim_do_antigo(self):
        self.conferir("um\ndois\ntres", "um\ndois\ntres\n")

    def test_sem_quebra_no_fim_do_novo(self):
        self.conferir("um\ndois\ntres\n", "um\ndois\ntres")

    def test_sem_quebra_nos_dois(self):
        self.conferir("um\ndois\ntres", "um\ndois\nTRES")

    def test_ultima_linha_ganha_quebra_por_ter_ganhado_vizinha(self):
        # A última linha do antigo não tem quebra; no novo ela continua igual
        # mas ganhou uma linha depois — então ganhou quebra também, e não pode
        # sair como contexto.
        self.conferir("um\ndois", "um\ndois\ntres\n")

    def test_contexto_zero(self):
        a = "".join(f"linha {i}\n" for i in range(15))
        b = a.replace("linha 3\n", "").replace("linha 9\n", "MUDOU\n")

        self.conferir(a, b, contexto=0)

    def test_varios_contextos(self):
        a = "".join(f"linha {i}\n" for i in range(30))
        b = a.replace("linha 10\n", "MUDOU\n")

        for contexto in (0, 1, 2, 3, 5, 10):
            with self.subTest(contexto=contexto):
                self.conferir(a, b, contexto=contexto)

    def test_a_secao_depois_do_arroba(self):
        # O texto após o segundo `@@` é a declaração em que a mudança caiu.
        # O corpo precisa ser mais longo que o contexto: com uma função de
        # cinco linhas o trecho começa na linha 1 e não sobra nada acima dele
        # para citar.
        corpo_longo = "".join(f"    passo {i}\n" for i in range(10))
        a = "def somar(a, b):\n" + corpo_longo + "    return a + b\n"
        b = a.replace("    passo 7\n", "    passo SETE\n")

        patch = self.conferir(a, b)

        self.assertIn("@@ def somar(a, b):", patch)

    def test_arquivos_iguais_nao_geram_nada(self):
        self.assertEqual(unificado("a\nb\n", "a\nb\n"), "")

    def test_mil_arquivos_sorteados(self):
        """O teste que realmente sustenta o projeto.

        Um exemplo escolhido a dedo prova que aquele caso funciona. Mil pares
        sorteados, com contexto variado e a quebra final sorteada, provam que a
        implementação concorda com o git em toda a superfície que os dois têm
        em comum.
        """
        sorteio = random.Random(20260925)
        conferidos = 0

        for _ in range(1000):
            quantas = sorteio.randint(0, 30)

            if sorteio.random() < 0.5:
                base = [f"linha {i}" for i in range(quantas)]
            else:
                base = [
                    f"def f{i}():" if i % 4 == 0 else f"    passo {i}"
                    for i in range(quantas)
                ]

            novo = list(base)

            for _ in range(sorteio.randint(0, 6)):
                if not novo or sorteio.random() < 0.4:
                    novo.insert(sorteio.randint(0, len(novo)), f"novo {sorteio.randint(0, 99)}")
                elif sorteio.random() < 0.5:
                    novo.pop(sorteio.randrange(len(novo)))
                else:
                    novo[sorteio.randrange(len(novo))] = f"    mudado {sorteio.randint(0, 99)}"

            antigo = "\n".join(base) + ("\n" if base and sorteio.random() < 0.8 else "")
            depois = "\n".join(novo) + ("\n" if novo and sorteio.random() < 0.8 else "")
            contexto = sorteio.choice([0, 1, 2, 3, 5, 7])

            meu = unificado(antigo, depois, contexto=contexto)
            doGit = self.git_diff(antigo, depois, contexto)

            self.assertEqual(
                corpo(meu),
                corpo(doGit),
                f"divergiu com contexto {contexto}\nantigo={antigo!r}\nnovo={depois!r}",
            )

            # De quebra: o patch tem de aplicar e reverter direito.
            if meu:
                self.assertEqual(aplicar(antigo, meu), depois)
                self.assertEqual(reverter(depois, meu), antigo)

            conferidos += 1

        self.assertEqual(conferidos, 1000)


@unittest.skipUnless(TEM_GIT, "o git não está instalado")
class TestOGitAceitaOQueEuGero(unittest.TestCase):
    """A outra direção: o `git apply` aceita e acerta os meus patches.

    Bater byte a byte já é forte, mas é uma comparação de texto. Isto é a
    prova de uso: uma ferramenta de verdade pega o patch, aplica, e o
    resultado é o arquivo que eu disse que seria.
    """

    def setUp(self):
        self.pasta = Path(tempfile.mkdtemp(prefix="diferenca-apply-"))

        subprocess.run(["git", "init", "-q"], cwd=self.pasta, check=True)
        subprocess.run(
            ["git", "config", "core.autocrlf", "false"], cwd=self.pasta, check=True
        )

    def tearDown(self):
        shutil.rmtree(self.pasta, ignore_errors=True)

    def aplicar_com_git(self, antigo: str, novo: str):
        alvo = self.pasta / "arquivo.txt"

        alvo.write_bytes(antigo.encode("utf-8"))

        patch = unificado(antigo, novo, "a/arquivo.txt", "b/arquivo.txt")

        if not patch:
            return

        (self.pasta / "mudanca.patch").write_bytes(patch.encode("utf-8"))

        resultado = subprocess.run(
            ["git", "-c", "core.autocrlf=false", "apply", "--unsafe-paths", "mudanca.patch"],
            cwd=self.pasta,
            capture_output=True,
            text=True,
        )

        self.assertEqual(resultado.returncode, 0, f"o git recusou o patch:\n{resultado.stderr}\n{patch}")
        self.assertEqual(alvo.read_bytes().decode("utf-8"), novo)

    def test_troca_simples(self):
        self.aplicar_com_git("um\ndois\ntres\n", "um\nDOIS\ntres\n")

    def test_insercao_e_remocao(self):
        a = "".join(f"linha {i}\n" for i in range(20))
        b = a.replace("linha 3\n", "").replace("linha 15\n", "linha 15\nEXTRA\n")

        self.aplicar_com_git(a, b)

    def test_sem_quebra_no_fim(self):
        self.aplicar_com_git("um\ndois\ntres", "um\nDOIS\ntres")

    def test_ganhando_a_quebra_do_fim(self):
        self.aplicar_com_git("um\ndois", "um\ndois\n")

    def test_perdendo_a_quebra_do_fim(self):
        self.aplicar_com_git("um\ndois\n", "um\ndois")

    def test_cem_sorteados(self):
        sorteio = random.Random(7)

        for _ in range(100):
            base = [f"linha {i}" for i in range(sorteio.randint(1, 20))]
            novo = list(base)

            for _ in range(sorteio.randint(1, 5)):
                if sorteio.random() < 0.4:
                    novo.insert(sorteio.randint(0, len(novo)), f"novo {sorteio.randint(0, 99)}")
                elif len(novo) > 1 and sorteio.random() < 0.5:
                    novo.pop(sorteio.randrange(len(novo)))
                else:
                    novo[sorteio.randrange(len(novo))] = f"mudado {sorteio.randint(0, 99)}"

            antigo = "\n".join(base) + ("\n" if sorteio.random() < 0.8 else "")
            depois = "\n".join(novo) + ("\n" if sorteio.random() < 0.8 else "")

            with self.subTest(antigo=antigo, novo=depois):
                self.aplicar_com_git(antigo, depois)


if __name__ == "__main__":
    unittest.main()

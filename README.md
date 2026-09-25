# diferenca

Diff unificado escrito do zero em Python puro, pelo algoritmo de Myers — o
mesmo que o `git diff`, o `diff` do GNU e o `difflib` usam.

A saída é **idêntica byte a byte à do `git diff`**, e não é força de expressão:
os testes rodam o git de verdade e comparam.

```
$ python -m diferenca diff antes.py depois.py
--- a/antes.py
+++ b/depois.py
@@ -1,5 +1,5 @@ def total(itens):
 def total(itens):
     soma = 0
     for item in itens:
-        soma = soma + item.preco * item.qtd
-    return soma
+        soma = soma + item.preco * item.qtd + item.imposto
+    return round(soma, 2)
```

```
$ python -m diferenca diff --palavras antes.py depois.py
-        soma = soma + item.preco * item.qtd
-    return soma
+        soma = soma + item.preco * item.qtd{+ + item.imposto+}
+    return {+round(+}soma{+, 2)+}
```

## A mudança de pergunta

A pergunta ingênua é *"qual a maior subsequência comum entre os dois
arquivos?"*. Ela se resolve com uma tabela de N×M células — para dois arquivos
de dez mil linhas, **cem milhões de células**, preenchidas mesmo quando os
arquivos diferem em uma linha só.

A pergunta de Myers é *"qual o menor número de edições?"*. Chamando esse número
de D, o custo é O((N+M)·D). A troca compensa porque **em diff de código D é
pequeno**: arquivos parecidos é o caso comum, não o excepcional.

Medido aqui, em 10.000 linhas:

| | D | tempo |
|---|---|---|
| 3 linhas mudadas | 5 | **33 ms** |
| uma linha em cada três mudada | 6.668 | **35 s** |

A segunda linha da tabela não é um defeito escondido — é o algoritmo fazendo
exatamente o que promete, e está nos limites lá embaixo.

### A geometria

Imagine um grid: andar para a direita apaga uma linha do arquivo antigo, andar
para baixo insere uma do novo, e andar na diagonal é uma linha igual — de
graça. O diff é o caminho mais barato de um canto ao outro. Myers explora esse
grid por diagonais, uma frente de onda por vez, e a primeira frente que alcança
o canto tem o D mínimo.

Guardar a frente inteira para reconstruir o caminho custa O(D²) de memória. A
versão implementada aqui é a **refinação em espaço linear**: avança uma frente
de cada ponta até que elas se cruzem, acha o ponto do meio do caminho e resolve
as duas metades por recursão. A memória cai para O(N+M).

## Os oráculos

Um diff é fácil de acreditar que está certo, porque a saída *parece* boa. Este
projeto não confia nisso em nenhum lugar.

### 1. O `git diff` de verdade

**Mil pares de arquivos sorteados**, com contexto de 0 a 7 e a quebra de linha
final sorteada nos dois lados, passam pelo `git diff --no-index` e pelo código
daqui, e as duas saídas têm de ser iguais **byte a byte**. Onde esse teste
passa, não sobra espaço para "é equivalente".

### 2. O `git apply` de verdade

A outra direção: o git pega os patches gerados aqui, aplica num repositório de
verdade, e o arquivo resultante tem de ser exatamente o esperado. Bater texto é
uma coisa; ser aceito por uma ferramenta é outra.

### 3. A conta ingênua, escrita à parte

A maior subsequência comum determina sozinha a distância mínima, por
`D = (N − L) + (M − L)`. O teste calcula L por programação dinâmica — lenta,
quadrática e obviamente correta — e exige que Myers dê o mesmo D, em **4.500
pares sorteados**. É uma prova de minimalidade, não uma comparação de gosto.

### 4. A ida e volta

Gerar o diff e aplicá-lo tem de devolver **exatamente** o outro arquivo, e
revertê-lo tem de devolver o primeiro. **Oito mil pares.** Não é comparação de
texto: é a definição de estar certo.

## O `difflib` da biblioteca padrão não é minimal

Um dos testes ia comparar o total de linhas em comum com o do
`difflib.SequenceMatcher`. Ele falhou — e quem estava errado era a expectativa.

O `SequenceMatcher` não usa Myers: é um casamento guloso de maiores blocos, no
estilo Ratcliff/Obershelp, e **não garante a maior subsequência comum**. Em
`dbbbccc` contra `cababdddcbd` ele acha 2 linhas em comum onde existem 3.

O teste virou uma desigualdade — nunca menos que o difflib, e às vezes mais —
com a conta por programação dinâmica confirmando que o "mais" é o certo.

## Quatro armadilhas do formato unificado

Todas apareceram comparando com o git, nenhuma pensando no assunto.

**1. O cabeçalho conta em base 1, mas arquivo vazio começa em 0.**
`@@ -0,0 +1,3 @@` é um arquivo criado. `@@ -1,0 ...` não existe.

**2. Contagem 1 é omitida.** `@@ -5 +5,2 @@`, não `@@ -5,1 +5,2 @@`. Quem sempre
escreve a vírgula gera um patch que o `patch` aceita e que não bate com o do
git.

**3. O número do lado vazio vem da posição, não de uma linha.** Um trecho de
remoção pura não tem nenhuma linha do lado novo — tirar o número de uma linha
que não existe dá zero, quando o certo é "logo depois da última linha nova que
já saiu". Só aparece com `-U0`, e é aí que fica claro que **contar** é o jeito
certo nos dois casos.

**4. A quebra de linha do fim é uma mudança.** E não só no caso óbvio: se a
última linha do arquivo antigo não tinha quebra e no novo ela continua igual
mas ganhou uma linha depois, ela **ganhou uma quebra** sem ninguém mexer no
texto dela — e deixa de poder ser uma linha de contexto. Vira `-linha` seguida
de `+linha`, com a marca `\ No newline at end of file` no lado a que ela
pertence.

## O texto depois do segundo `@@`

Não é comentário: é a declaração dentro da qual a mudança caiu, e é o que
permite ler um diff grande sem abrir o arquivo. A regra padrão do git é
despretensiosa e funciona em quase toda linguagem: subindo a partir da linha
anterior ao trecho, **a primeira que começa com letra, `_` ou `$`**. Como corpo
de função vem indentado e linha em branco não começa com letra, o que sobra é
justamente a declaração mais recente.

## Os defeitos que os testes acharam

Vale registrar, porque os quatro são de tipos diferentes.

**O vetor das frentes de onda estourava.** Eu o dimensionei pelo intervalo das
diagonais (de −m a +n), mas os índices realmente consultados vão além disso.
Só quebra quando os dois lados têm tamanhos bem diferentes — e o teste que o
pegou compara arquivos de 0 e 40 linhas.

**O caso base supunha que a última edição estava na ponta.** Com uma edição só
sobrando, o código emitia a diagonal e depois a edição. A contagem saía certa e
o conteúdo trocado — o pior tipo de defeito, porque a distância mínima continua
batendo e só a reconstrução denuncia.

**A marca de "sem quebra" era tratada igual dos dois lados.** Ela descreve a
linha imediatamente acima: depois de um `-` fala do arquivo antigo e não diz
nada sobre o resultado. Tratar as duas iguais errava justamente nos dois
sentidos em que o caso importa.

**A semelhança entre linhas contava os espaços.** Duas linhas sem nada em comum
mas com a mesma indentação dividiam todos os espaços em branco;
`aaaa bbbb cccc` contra `zzzz yyyy xxxx` dava 0,4 — o bastante para marcar
palavra a palavra duas linhas que não têm palavra nenhuma em comum.

## Rodando

Não há o que instalar. Python 3.12 ou mais novo, nenhuma dependência.

```bash
python -m diferenca diff antes.txt depois.txt
python -m diferenca diff -U0 antes.txt depois.txt       # sem contexto
python -m diferenca diff --palavras antes.txt depois.txt
python -m diferenca contar antes.txt depois.txt

python -m diferenca aplicar arquivo.txt mudanca.patch --no-lugar
python -m diferenca reverter arquivo.txt mudanca.patch
```

O `diff` sai com código **1** quando há diferença e **0** quando não há, como o
`diff` de sempre — é com isso que um script conta.

Como biblioteca:

```python
from diferenca import unificado, aplicar, reverter, distancia

patch = unificado(antigo, novo, "a/x.py", "b/x.py")

aplicar(antigo, patch) == novo      # True
reverter(novo, patch) == antigo     # True

distancia(antigo.splitlines(), novo.splitlines())   # o D mínimo
```

## Testes

```bash
python -m unittest discover -s testes -t . -v
```

124 testes. Leva cerca de 80 segundos, e quase tudo isso são os mil processos
do `git diff` — é o preço de ter um juiz que não é meu.

## Estrutura

```
diferenca/myers.py       o algoritmo, em espaço linear
diferenca/unificado.py   o formato: cabeçalhos, agrupamento, quebra final
diferenca/aplicar.py     aplicar e reverter um patch
diferenca/palavras.py    diferença dentro da linha
diferenca/cli.py         a linha de comando
testes/test_contra_o_git.py   o oráculo principal
```

## Limites conhecidos

- **O custo acompanha o tamanho da diferença, e isso tem um lado ruim.** Dois
  arquivos muito diferentes são o pior caso: 10.000 linhas com um terço delas
  trocadas levam **35 segundos** aqui. O git resolve isso desistindo da
  minimalidade quando D passa de um limite; este projeto não desiste, e por
  isso demora.
- **Sem a heurística de indentação do git.** Entre vários diffs igualmente
  mínimos, o git desliza o trecho para alinhar com linhas em branco e
  indentação, o que produz diffs mais legíveis. É um passo *depois* do
  algoritmo, e não está implementado — por isso os testes passam
  `--no-indent-heuristic` ao git.
- **Um arquivo por vez.** Não há `diff --git`, `index`, modo de arquivo, renome
  nem diff de diretório. O que entra e sai é o corpo do patch.
- **Só texto.** Nada de detectar binário, e a leitura assume UTF-8.
- **O emparelhamento do `--palavras` é por posição.** Dentro de um bloco com o
  mesmo número de linhas de cada lado, a primeira removida vai com a primeira
  inserida. É um palpite, e com contagens diferentes ele não tenta.
- **Não lê patch com folga.** O `patch` de verdade procura o trecho algumas
  linhas acima e abaixo quando o arquivo mudou um pouco; aqui o contexto tem de
  bater exatamente, ou o patch é recusado.

## Onde ele se encaixa

Faz par com o [`mini-git`](https://github.com/condeDeveloper/mini-git), que
escreve os objetos do Git do zero — blob, tree e commit, com hashes idênticos
aos do git de verdade. Um monta o que o Git guarda; o outro mostra o que mudou
entre duas versões.

## Licença

MIT.

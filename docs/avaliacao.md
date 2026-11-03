<!-- GERADO POR tests/avaliar.py --md: nao editar dentro dos marcadores -->
# Avaliação — Artikel

Casos em `tests/casos_teste.csv`: **42** (marco 5 do cronograma).

## Métricas

| Métrica | Resultado | Meta | Situação |
|---|---|---|---|
| Acurácia de intenções | 0.952 | 0.85 | OK |
| Precisão@5 da recuperação | 0.886 | 0.60 | OK |
| Abstenção correta fora de escopo | 1.000 | 0.90 | OK |
| Citações inventadas | 0 | 0 | OK |

## Matriz de confusão

| esperado \ previsto | buscar_referencias | avaliar_fonte | formatar_referencia | orientar_busca | fora_de_escopo |
|---|---|---|---|---|---|
| buscar_referencias | 14 | 0 | 0 | 0 | 1 |
| avaliar_fonte | 0 | 7 | 0 | 0 | 0 |
| formatar_referencia | 0 | 0 | 5 | 0 | 0 |
| orientar_busca | 2 | 0 | 0 | 5 | 0 |
| fora_de_escopo | 0 | 0 | 0 | 0 | 8 |

## Casos que não passaram

| id | pergunta | esperado | previsto | confiança | resposta |
|---|---|---|---|---|---|
| 9 | Que palavras-chave uso para achar artigos sobre cárie infantil? | orientar_busca | buscar_referencias | 0.55 | esclarecimento |
| 20 | como faço para achar artigo sobre implante | orientar_busca | buscar_referencias | 0.63 | recomendacao |

<!-- FIM DO TRECHO GERADO -->

> **Atenção ao editar:** o trecho entre os dois marcadores acima é reescrito por
> `python tests/avaliar.py --md docs/avaliacao.md`. O texto daqui para baixo é escrito à mão
> e é preservado — antes dos marcadores, rodar o gerador apagava esta análise.

## Análise de 3 falhas e melhorias (exigência do Marco 5)

A rodada que motivou esta seção passou em todos os 30 casos originais (os casos 31–42, de
Medicina e Biologia, entraram em 23/10/2026; os erros atuais estão na tabela gerada acima),
então as falhas analisadas são as que apareceram no caminho — encontradas rodando `tests/avaliar.py` e os diagnósticos de
`scripts/diagnostico/`, todas corrigidas e fixadas por teste automatizado. Ficam registradas
porque o Marco 5 pede análise de erros, e porque são as que voltam se alguém mexer no
pré-processamento ou na recuperação.

### Falha 1 — Recall da área de Computação perto de zero

**Sintoma:** a coleta fechou Computação com **1 artigo** de 100 previstos, enquanto
Odontologia e Psicologia batiam a cota. O relatório de coleta mostrava `fora_do_tema`
descartando ~50% dos candidatos do Crossref e `licenca` descartando o resto.

**Diagnóstico:** o Crossref é forte em saúde e fraco em Computação: a busca por
"machine learning health" devolvia artigos de educação, engenharia civil e agricultura —
domínios vizinhos que passam no filtro de licença, mas não no filtro temático da semente.
Dos 200 candidatos, 14 passavam no filtro básico e **0** no temático.

**Melhoria:** o `Article Search` do DOAJ entrou como fonte complementar de artigos **só
para Computação** (`doaj.buscar_artigos`), filtrando por assunto LCC de Ciência da
Computação e usando `bibjson.year` no recorte. Como o Article Search não devolve licença, a
licença e a revisão por pares passaram a vir do cadastro do periódico
(`doaj.periodicos_computacao_cc`, uma requisição para os 314 periódicos do assunto).
Resultado: Computação foi de 1 para **46 artigos**. Risco residual: são periódicos de
acesso aberto com licença CC-BY/CC0, mas sem a conferência de área por LCC do DOAJ que as
outras fontes passam — a decisão está registrada em `docs/especificacao.md` e deve ser
confirmada no Marco 3.

### Falha 2 — Falso positivo por comparação de radical solta

**Sintoma:** na pergunta "Preciso de artigos sobre aprendizado de máquina na saúde", o
primeiro resultado era um artigo de Psicologia sobre desenvolvimento infantil.

**Diagnóstico:** a cobertura temática comparava o radical de 4–5 letras do termo com
`in` no texto do artigo. O radical de "maquina" (**maqui**) casa com "M**ARIANE**"
(m-a-r-i-a-n-e), então o artigo satisfazia a guarda temática e entrava na resposta.

**Melhoria:** a comparação passou a exigir **início de palavra**. Na reavaliação dos
retornos (abaixo) o casamento foi endurecido de novo, agora exigindo palavra inteira ou
flexão simples. Coberto por testes em `tests/test_recuperacao_periodicos.py`.

### Falha 3 — Domínio do classificador e Precisão@5 abaixo da meta

**Sintoma:** duas medições ligadas. (a) "cadê artigos sobre periodontia" era classificada
como `orientar_busca` (abstenção da FAQ) em vez de `buscar_referencias`. (b) A Precisão@5
ficou em **0,333**, com a meta em 0,60.

**Diagnóstico:** (a) o dataset tinha 24 frases por intenção, quase todas formais; a
pergunta coloquial da pergunta simulada 7 não tinha vizinho próximo no treino. (b) a busca
comparava a pergunta em português com um vocabulário majoritariamente em inglês: "clareamento
dental" não casava com "dental bleaching", e vencia o artigo que tinha a palavra literal no
título. Além disso, termos sem valor temático ("artigos", "preciso", "dental") dominavam a
similaridade.

**Melhorias (três, aplicadas juntas):**
1. dataset de intenções de 120 para **199 frases**, com formulações coloquiais por
   intenção, mantendo a faixa de 20–40 exigida e a regra de que frase de teste não entra no
   treino (verificado por `tests/test_intencoes.py`);
2. **expansão da consulta** com os equivalentes pt/en (`recuperacao.ALIASES`) e
   **cobertura temática ponderada por idf normalizado**, para que casar o termo raro
   ("clareamento") valha muito mais que casar o termo comum ("dental");
3. termos genéricos e qualificadores de contexto ("saúde", "paciente") saíram da conta de
   cobertura (`recuperacao.GENERICAS`).

Resultado: acurácia de intenções **1,000** e Precisão@5 **0,743**.

## Reavaliação dos retornos (relato do usuário)

Um teste manual com **"computação quântica"** devolveu artigos de Psicologia. Investigando,
o caso revelou duas falhas na recuperação — a descrição completa está em
[`pendencias.md`](pendencias.md), seção 5:

1. **Casamento de termo por radical curto.** "quântica" era cortado para `quant` e casava
   com "**quantitative**" em artigos de Psicologia.
2. **Bônus de curadoria como se fosse relevância.** O bônus (indexado + recente = 0,08)
   somava sobre uma similaridade de 0,06, levava o artigo a 0,14 e ele passava do limiar de
   score — inclusive artigos com **nenhuma** palavra da pergunta ("termos presentes: NENHUM"
   com score 0,14).

O limiar de cobertura temática subiu de 0,34 para **0,60**, valor escolhido com
`python scripts/diagnostico/_diag_limiar_cobertura.py`, que compara 10 perguntas que devem
achar artigo com 6 fora do recorte.

**Verificação contra a API real** (`_verificar_retornos.py`):

| Conjunto | Antes | Depois |
|---|---|---|
| Perguntas de dentro do escopo que recomendam | 6 de 6 | **6 de 6** |
| Perguntas fora do recorte que devolviam artigo | 5 de 8 | **0 de 8** |

As quatro métricas do quadro acima não mudaram com a correção.

## Como reproduzir

```bash
python -m pytest -q                                     # testes do motor e da coleta
python tests/avaliar.py --md docs/avaliacao.md           # este relatório
python scripts/diagnostico/_verificar_retornos.py 8000   # retornos contra a API no ar
python scripts/diagnostico/_diag_limiar_cobertura.py     # escolha do limiar de cobertura
python scripts/diagnostico/_diag_determinismo.py 8       # acusa número que muda sozinho
node web/_verificar_interface.js                         # a interface desenha o chat
node web/_verificar_contrato.js http://127.0.0.1:8000    # API real contra o que o front lê
```

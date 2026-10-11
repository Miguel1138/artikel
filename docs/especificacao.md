# Especificação consolidada — Artikel

Fonte: `Artikel — Documento unificado do projeto` (PDF de 13 páginas, 11/10/2026).
Este arquivo transforma as decisões já tomadas no documento em critérios verificáveis de
implementação. Onde o documento é omisso, a decisão nova está marcada com **[novo]**.

## 1. Identificação

| Campo | Valor |
|---|---|
| Projeto | Artikel — assistente de referências confiáveis para TCC |
| Disciplina | Inteligência Artificial · A3 Projeto Integrador · 40 pontos |
| Período | 10/10 a 05/12/2026, seis marcos |
| Tipo | Protótipo acadêmico com cenário e base curados pela equipe |
| Stack | Python (scikit-learn, FastAPI) na API · React na interface · sem LLM |
| Equipe | Miguel (gerente), Caue, Maria Elis, Ana Carolina |
| Patrocinador | Prof. Marcelo da Silva |

## 2. Problema e público

Estudantes de graduação perdem tempo e nota por usar referências frágeis no TCC. O Artikel
reduz esse risco limitando as recomendações a uma base verificada e se abstendo quando não
houver registro confiável.

Público: estudantes de Ciência da Computação, Odontologia e Psicologia em fase de projeto
ou escrita do TCC (perfis fictícios nos testes). Cinco dores mapeadas:

| # | Dor | Intenção que responde |
|---|---|---|
| 1 | Fontes não acadêmicas como referência principal | `avaliar_fonte` |
| 2 | Citações inventadas por assistentes generativos | `buscar_referencias` |
| 3 | Periódicos duvidosos (predatórios) | `avaliar_fonte` |
| 4 | Busca ineficiente em SciELO e Google Acadêmico | `orientar_busca` |
| 5 | Formatação ABNT NBR 6023 | `formatar_referencia` |

## 3. Objetivos

**Geral:** entregar, até o Marco 6, um chatbot executável que recomende artigos de uma base
curada e se abstenha quando não houver referência confiável.

| # | Objetivo específico | Marco |
|---|---|---|
| 1 | Construir e versionar base curada com metadados, origem e licença documentadas | 2 |
| 2 | Classificador de intenções próprio com 4+ intenções e classe fora de escopo | 4 |
| 3 | Recuperação por similaridade (TF-IDF ou BM25) com limiar e fallback | 4 |
| 4 | Referência ABNT de qualquer artigo da base por regras próprias | 4 |
| 5 | Avaliar com 20+ casos, calcular métricas e analisar 3 falhas | 5 |
| 6 | Relatório de 6+ páginas, README executável e demonstração ao vivo | 6 |

## 4. Escopo

**Dentro:** base de 150 a 300 artigos de acesso aberto em Computação, Odontologia e
Psicologia; cinco intenções; metadados (título, autores, ano, periódico, DOI, resumo,
palavras-chave, licença); contexto mínimo ("o segundo artigo"); interface React consumindo
a API.

**Fora:** texto completo dos artigos e resumo gerado de PDFs; redação, revisão ou paráfrase
de trechos do TCC; busca em tempo real em bases externas durante a conversa; login,
histórico por usuário ou dado pessoal real; orientação clínica ou terapêutica; garantia de
adequação ao tema.

### Contrato de intenções

| Intenção | Exemplo | Resposta esperada |
|---|---|---|
| `buscar_referencias` | "Preciso de artigos sobre aprendizado de máquina na saúde" | Top 3–5 artigos com ano, periódico, DOI e motivo |
| `avaliar_fonte` | "A revista X é confiável?" | Parecer pela lista curada (indexação, revisão por pares) ou "não consta na base" |
| `formatar_referencia` | "Me dá a referência ABNT do segundo artigo" | Referência NBR 6023 por regras, usando o contexto |
| `orientar_busca` | "Como procuro artigos no SciELO?" | Orientação curta da FAQ de busca |
| `fora_de_escopo` | "Escreve minha introdução" | Abstenção e encaminhamento ao orientador ou à biblioteca |

## 5. Requisitos do enunciado (R1–R7)

| Req. | Como o Artikel atende | Evidência no repositório |
|---|---|---|
| R1 — Conversação | Interface React consumindo a API; memória da última lista exibida | `web/`, `app/contexto.py` |
| R2 — Domínio | 5 intenções; base de artigos, lista de periódicos e FAQ curadas | `data/` |
| R3 — IA implementada | Classificador treinado pela equipe + recuperação TF-IDF/BM25 com reordenação por curadoria | `app/intencoes.py`, `app/recuperacao.py` |
| R4 — Fluxo completo | Entrada → normalização → intenção → busca/regra → resposta ou abstenção, com traço da decisão | `app/fluxo.py` |
| R5 — Validação | 30 casos (meta acima dos 20): esperadas, reformulações, ambíguas, fora de escopo | `tests/casos_teste.csv` |
| R6 — Métricas | Acurácia e matriz de confusão; Precisão@5; taxa de abstenção correta | `tests/avaliar.py` |
| R7 — Autoria | README, base versionada sem chave de API, scripts de coleta e testes, registro de contribuições | `README.md`, `docs/contribuicoes.md` |

## 6. Arquitetura (Opção C — híbrida)

Um classificador de intenções treinado pela equipe decide o caminho; cada caminho responde
por recuperação ou por regras, e o bot nunca gera texto livre com referências.

| Módulo | Arquivo | Função |
|---|---|---|
| Pré-processamento | `app/preprocessamento.py` | Minúsculas, acentos e stopwords; igual no treino e na inferência |
| Classificador | `app/intencoes.py` | TF-IDF + Regressão Logística (alt.: Naive Bayes); dataset `intents.csv`; retorna classe e probabilidade |
| Recuperação | `app/recuperacao.py` | TF-IDF ou BM25 sobre título + resumo + palavras-chave; cosseno; reordena por revisão por pares, ano e indexação |
| Regras ABNT | `app/abnt.py` | Monta a referência NBR 6023 a partir dos campos, com múltiplos autores; sem LLM |
| Periódicos e FAQ | `app/periodicos.py`, `app/faq.py` | Consulta `periodicos.json` e `faq_busca.json`; fora da lista → "não consta na base" |
| Contexto | `app/contexto.py` | Guarda a última lista exibida para resolver "o segundo artigo" (R1) |
| Orquestrador | `app/fluxo.py` | Único ponto que encadeia módulos, aplica limiares e gera o traço da decisão (R4) |
| Configuração | `app/config.py` | Concentra os limiares, para ajuste no Marco 5 |
| Abstenção | `app/abstencao.py` | Textos e regras de abstenção/encaminhamento **[novo: separado do fluxo para ser testável]** |

**Alternativas descartadas:** Opção D (LLM + recuperação) reintroduz o risco de citação
inventada e, sozinha, não cumpre R3; VADER faz análise de sentimento, não classificação de
intenção.

> **Diagrama do documento:** "fluxo do Artikel · **3 módulos, 2 pontos de abstenção**" —
> buscar_referencias vai à recuperação, formatar_referencia às regras ABNT, avaliar_fonte e
> orientar_busca à lista de periódicos e à FAQ; fora_de_escopo ou confiança baixa terminam
> em abstenção. Os "3 módulos" do diagrama são Pré-processamento, Classificador e
> Recuperação; na implementação a Recuperação se desdobra em `recuperacao.py` (busca) e
> `abnt.py` (regras), como a própria tabela de módulos do documento prevê. Os "2 pontos de
> abstenção" são o limiar de confiança do classificador e o limiar de score da recuperação —
> e há ainda a abstenção por escopo e as duas previstas em `formatar_referencia` (sem
> contexto) e em `orientar_busca` (fora do roteiro da FAQ). O fluxograma completo está em
> [`fluxograma.md`](fluxograma.md).

## 7. Dados e coleta (Marco 2)

A base é coletada uma vez por `scripts/coleta/pipeline.py`, versionada em `data/` e nunca
consultada em fontes externas durante a conversa; nenhuma fonte exige chave de API.

| Fonte | Papel | Áreas | Script |
|---|---|---|---|
| Crossref | Principal: busca, validação de DOI e enriquecimento; prevalece em conflitos | As três | `crossref.py` |
| SciELO (ArticleMeta) | Artigos brasileiros de periódicos revisados por pares | As três | `scielo.py` |
| Europe PMC | Complemento | Odontologia, Psicologia | `europepmc.py` |
| DOAJ | Indexação e assunto LCC do periódico; base de `avaliar_fonte`. **Também busca de artigos em Computação** | As três (artigos: Computação) | `doaj.py` |
| NLM Catalog (MEDLINE) | Indexação adicional aceita (`ACEITAR_MEDLINE = True`) | As três | `medline.py` |

> **Desvio registrado [novo]:** o Crossref não sustenta a área de Computação no recorte
> temático — a busca devolve resultados de áreas vizinhas (educação, engenharia) que não
> passam pelo filtro da semente, e a coleta fechou Computação com 1 artigo. Como o DOAJ
> indexa por assunto LCC e permite buscar no resumo, o `Article Search` do DOAJ entrou como
> fonte complementar **de artigos** para Computação. É a mesma base já usada em
> `avaliar_fonte`, continua de acesso aberto e é filtrada por assunto de Ciência da
> Computação. A decisão deve ser confirmada no Marco 3.

**Descartados:** Google Scholar como fonte automática (só descoberta manual; entra pelo DOI)
e OpenAlex (exige chave desde 13/02/2026; snapshot de ~750 GB desproporcional).

**Pipeline ETL**

1. **Extract:** por área e semente, consulta Crossref (pt e en), Europe PMC e todos os
   artigos SciELO dos periódicos da área; brutos em cache em `data/raw/`.
2. **Transform:** filtro básico (DOI, período, idioma, licença) → filtro temático pela
   semente (radical de 5 caracteres) → dedup por DOI com mescla → validação e enriquecimento
   no Crossref → refiltro → exige indexação DOAJ, SciELO ou MEDLINE → conferência de área
   (LCC ou área WoS).
3. **Load:** grava `knowledge_base.json`, `periodicos.json` e `relatorio_coleta.md` com o
   funil de descartes por semente.

**Recorte:** 2020–2026; idiomas pt, en; licenças CC-BY e CC0 (SA/NC/ND fora); cota 4
sementes × 25 = 100 artigos por área; 100 candidatos por consulta; máx. 300 artigos por
periódico SciELO; LCC Computação QA75, QA76, R858 · Odontologia RK · Psicologia BF; áreas
WoS COMPUTER SCIENCE · DENTISTRY · PSYCHOLOGY.

**Esquema da base:** `id, doi, titulo, autores, ano, periodico, issn, volume, numero,
paginas, resumo, palavras_chave, idioma, licenca, area, fonte, url, data_coleta`.
Coleção de documentos JSON desnormalizada (star schema descartado: é recuperação, não data
warehouse).

**Sementes** (as marcadas com * vêm das perguntas simuladas):

| Área | Sementes |
|---|---|
| Computação | aprendizado de máquina saúde*, processamento de linguagem natural, segurança da informação, engenharia de software |
| Odontologia | clareamento dental*, cárie infantil*, doença periodontal, implantes dentários |
| Psicologia | ansiedade universitários*, depressão, saúde mental trabalho, desenvolvimento infantil |

**Estado da coleta:** o documento registrava, em cache, **3 periódicos SciELO de
Computação, 13 de Odontologia e 19 de Psicologia**, e já apontava que Computação tem poucos
periódicos SciELO e depende mais do Crossref — foi exatamente o que a coleta confirmou
(seção de desvio acima). O estado final está em `data/relatorio_coleta.md`.

## 8. Repositório

| Pasta | Conteúdo |
|---|---|
| `data/` | `raw/`, `knowledge_base.json`, `periodicos.json`, `faq_busca.json`, `intents.csv`, `relatorio_coleta.md` |
| `scripts/coleta/` | `config_coleta.py`, `comum.py`, `crossref.py`, `scielo.py`, `europepmc.py`, `doaj.py`, `medline.py`, `pipeline.py` |
| `scripts/` | `treinar_classificador.py` |
| `scripts/diagnostico/` | scripts de apoio, não importados pelo sistema: `_verificar_api.py`, `_diag_recuperacao.py`, `_diag_match.py`, `_diag_cache.py` |
| `app/` | `main.py`, `config.py`, `schemas.py`, `fluxo.py`, `preprocessamento.py`, `intencoes.py`, `recuperacao.py`, `abnt.py`, `periodicos.py`, `faq.py`, `contexto.py`, `abstencao.py` |
| `models/` | `intencoes.joblib` |
| `tests/` | `casos_teste.csv`, `test_*.py`, `avaliar.py` |
| `docs/` | `especificacao.md`, `avaliacao.md`, `contribuicoes.md`, `fluxograma.md`, `pendencias.md`, `fluxograma.png` (a gerar do Mermaid) |
| `web/` | interface React (`index.html`, `app.jsx`, `estilo.css`, `README.md`) |

**Dependências (`requirements.txt`):** `requests` (coleta); `xylose` (biblioteca oficial da
coleção SciELO, usada em conferência manual — o cliente do projeto não depende dela);
`scikit-learn`, `joblib`, `numpy`, `rank-bm25` (alternativa ao TF-IDF na recuperação);
`fastapi`, `uvicorn`; `pytest`, `pandas`. A pendência "adicionar `xylose` ao
`requirements.txt`" está resolvida.

## 9. Avaliação

30 casos de teste: as 11 perguntas simuladas entram como "esperadas" e 19 derivadas delas
cobrem reformulações, ambíguas e fora de escopo. Frases de teste nunca entram no treino.

**Perguntas simuladas (Marco 1)** — com a área e a dor de origem, e onde cada uma vive no
repositório:

| # | Pergunta | Intenção | Área | Dor | Caso no repositório |
|---|---|---|---|---|---|
| 1 | Preciso de artigos sobre aprendizado de máquina na saúde | `buscar_referencias` | Computação | 2 | caso 1 |
| 2 | A revista X é confiável? | `avaliar_fonte` | Todas | 3 | caso 2 |
| 3 | Me dá a referência ABNT do segundo artigo | `formatar_referencia` | Todas | 5 | caso 3 (com a variante "referência ABNT do segundo artigo") |
| 4 | Como procuro artigos no SciELO? | `orientar_busca` | Todas | 4 | caso 4 |
| 5 | Escreve minha introdução | `fora_de_escopo` | Todas | — | caso 5 |
| 6 | Quero artigos sobre ansiedade em universitários | `buscar_referencias` | Psicologia | 2 | caso 6 |
| 7 | Tem estudos recentes sobre clareamento dental? | `buscar_referencias` | Odontologia | 2 | caso 7 |
| 8 | Posso citar a Wikipédia no meu TCC? | `avaliar_fonte` | Todas | 1 | caso 8 |
| 9 | Que palavras-chave uso para achar artigos sobre cárie infantil? | `orientar_busca` | Odontologia | 4 | caso 9 |
| 10 | Qual remédio tomar para ansiedade? | `fora_de_escopo` | Psicologia | — | caso 10 |
| 11 | Ajuste o meu texto | `fora_de_escopo` | Todas | — | caso 11 |

A 3 é a única que depende de contexto (R1); a 10 testa o limite clínico. Nenhuma das 11
frases aparece no dataset de treino (`data/intents.csv`) — a verificação é automática, em
`tests/test_intencoes.py::test_frases_do_teste_nao_estao_no_treino`.

**Métricas e metas**

| Métrica | Meta | Como medir |
|---|---|---|
| Acurácia de intenções | ≥ 85% | Casos separados do treino, com matriz de confusão |
| Precisão@5 da recuperação | ≥ 0,6 | Relevância julgada por dois integrantes, de forma independente |
| Abstenção correta fora de escopo | ≥ 90% | Casos fora de escopo que terminam em abstenção |
| Citações inventadas | 0 | Toda referência exibida existe na base com DOI ou link |
| Referência ABNT correta | ≥ 90% | Conferência manual contra a NBR 6023 |

Metas propostas pela equipe, a confirmar no Marco 3, junto com os limiares de confiança e
de score.

## 10. Cronograma e papéis

O projeto vai de 10/10 a 05/12/2026 em seis marcos; o próximo é o **Marco 2 (Dados)**, em
17/10. M4 (protótipo) e M5 (avaliação) ficam a **uma semana de distância**, então os testes
precisam estar prontos antes do código final.

| Marco | Entrega verificável |
|---|---|
| 1 — Problema | TAP, persona, 5 dores, objetivo, limites e perguntas simuladas |
| 2 — Dados | Base, lista de periódicos e FAQ versionadas; origem, licença e critérios de curadoria |
| 3 — Técnica | Arquitetura justificada, comparação com a Opção D, fluxograma e limiares |
| 4 — Protótipo | Código executável, interface, README e registro de contribuições |
| 5 — Avaliação | Planilha de 30 testes, métricas, análise de 3 falhas e melhorias |
| 6 — Defesa | Relatório de 6+ páginas, repositório/ZIP e demonstração de 8 minutos |

| Papel | Responsabilidade verificável |
|---|---|
| Levantamento e base | Script de coleta, curadoria, lista de periódicos, FAQ e licenças |
| Implementação e integração | Classificador, recuperação, regras ABNT e fluxo |
| Dados e testes | Dataset de intenções, 30 casos, métricas e análise de erros |
| Interface, documentação e validação | Interface, README, relatório e roteiro da demonstração |

**Partes interessadas:** o professor aprova e avalia; estudantes de TCC são o público;
orientadores e biblioteca (simulados) recebem os encaminhamentos.

## 11. Premissas, restrições e riscos

**Premissas (validar no Marco 2):** metadados de acesso aberto podem ser redistribuídos com
a licença registrada; a equipe consegue julgar relevância para a Precisão@5; 150–300
artigos bastam para resultados distintos por tema.

**Restrições:** Python; ferramentas gratuitas ou locais; mecanismo de IA próprio (serviço
pronto sozinho não cumpre R3); nenhum dado pessoal real; nenhuma chave de API no
repositório; integração externa só com aprovação do professor; execução só com o README;
relatório de 6+ páginas; defesa de 8 minutos com pergunta inédita; uso de IA generativa
declarado.

| Risco | Impacto | Resposta |
|---|---|---|
| Licença de resumos impede redistribuição | Alto | Só CC-BY/CC0 registrada; em último caso, apenas título e palavras-chave |
| Base pequena ou concentrada | Alto | Cota de 25 artigos por semente e 100 por área |
| Recomendação de periódico predatório | Alto | Exigir indexação DOAJ, SciELO ou MEDLINE |
| Poucos exemplos para o classificador | Médio | 20–40 frases por intenção; treino e teste separados desde o início |
| Relevância subjetiva | Médio | Dois juízes independentes com critério registrado |
| Viés de idioma (maioria em inglês) | Médio | Documentar proporção; testar perguntas pt contra artigos en |
| Aumento de escopo | Médio | Inclusões passam pelo Fora do escopo e por acordo da equipe |
| Contribuição desigual | Médio | Commits e tarefas por pessoa desde o Marco 1 |
| Fonte muda política de acesso | Baixo | Base versionada; chatbot não depende das fontes em execução |

### Como os riscos foram tratados na implementação

| Risco | Evidência |
|---|---|
| Licença de resumos | 246 dos 246 artigos com licença registrada (100% CC-BY); o relatório de coleta traz a licença por fonte |
| Base pequena ou concentrada | 246 artigos, 107 periódicos, ~82 artigos por área; a cota por semente foi aplicada e o funil está em `data/relatorio_coleta.md` |
| Periódico predatório | Toda recomendação passa pela lista curada com indexação DOAJ/SciELO/MEDLINE; `avaliar_fonte` responde "não consta na base" fora dela |
| Poucos exemplos | 199 frases, 39–40 por intenção; `tests/test_intencoes.py` reprova se sair da faixa de 20–40 ou se frase de teste entrar no treino |
| Relevância subjetiva | `tests/avaliar.py` mede a Precisão@5 com o tema esperado anotado por caso; falta o segundo juiz (pendência 8 de `docs/pendencias.md`) |
| Viés de idioma | Proporção atual: **206 artigos em inglês e 40 em português**. O risco se materializou nos testes: "clareamento dental" não casava com "dental bleaching". A resposta foi a expansão pt/en da consulta em `recuperacao.ALIASES`, e o caso 7 do teste cobre exatamente isso (recall 5 de 5 no top 5) |
| Aumento de escopo | O desvio do DOAJ (só leitura, só Computação) foi o único acréscimo; está registrado na seção 7 e precisa de confirmação no Marco 3 |
| Fonte muda política | A base é versionada em `data/`; nada é consultado em tempo de conversa |
| Contribuição desigual | Médio | Commits e tarefas por pessoa desde o Marco 1 |
| Fonte muda política de acesso | Baixo | Base versionada; chatbot não depende das fontes em execução |

## 12. Pendências declaradas no documento

1. Distribuir os quatro papéis entre os integrantes (TAP ainda "a definir").
2. Registrar a licença de cada fonte de metadados (Marco 2).
3. Avisar o professor que a coleta usa APIs públicas só de leitura, fora do chatbot.
4. Adicionar `xylose` ao `requirements.txt`.
5. Conferir nomes de atributos do `xylose` contra a coleção do Insomnia (`scielo.py`).
6. Tratar `from`/`until` do ArticleMeta, que filtram data de processamento e não de
   publicação.
7. Escrever `faq_busca.json` e `intents.csv` (20–40 frases por intenção).
8. Definir limiares de confiança e de score no Marco 3.
9. Colher assinaturas de aprovação do TAP (professor e gerente).

### Situação das pendências neste repositório

| # | Situação |
|---|---|
| 2 | Resolvido: `data/periodicos.json` guarda `indexacao`, `revisao` e `licenca` por periódico, e o relatório de coleta traz a licença por fonte |
| 4 | Resolvido: `xylose` está em `requirements.txt` |
| 5 | Resolvido por outro caminho: o `scielo.py` deixou de usar `xylose` e passou a ler o JSON bruto do ArticleMeta, com os códigos de campo mapeados no topo do arquivo — não há mais atributo de biblioteca para conferir contra a coleção do Insomnia |
| 6 | Resolvido: o filtro de período usa `publication_date` (campo `v65`) do artigo, não `from`/`until` |
| 7 | Resolvido: `data/intents.csv` (39–40 frases por intenção, dentro da faixa de 20–40) e `data/faq_busca.json` (12 entradas) |
| 8 | Parcial: valores iniciais em `app/config.py`, com comentário de revisão no Marco 3 |
| 1, 3, 9 | Dependem de pessoas: seguem em `docs/contribuicoes.md` e no README |

## Situação da implementação (11/10/2026)

O que o documento já tinha decidido está implementado e medido:

| Item | Situação |
|---|---|
| Base curada (Marco 2) | 246 artigos, 107 periódicos, 100% CC-BY, nas três áreas |
| Classificador (R3, objetivo 2) | TF-IDF + Regressão Logística, 199 frases, acurácia 1,000 |
| Recuperação (objetivo 3) | TF-IDF/cosseno + cobertura temática ponderada + reordenação por curadoria, Precisão@5 0,743 |
| Regras ABNT (objetivo 4) | NBR 6023 por regras, 11 testes cobrindo os casos da norma |
| Fluxo e traço da decisão (R4) | `app/fluxo.py`, com intenção, confiança, ação e regra em toda resposta |
| Avaliação (objetivo 5) | 30 casos, 4 métricas na meta, análise das 3 falhas do caminho |
| Interface (R1) | `web/` consumindo a API, com painel do traço da decisão |

Pendências abertas e o registro do problema de permissões do ambiente estão em
[`docs/pendencias.md`](pendencias.md).

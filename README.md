# Artikel — assistente de referências confiáveis

Chatbot acadêmico que recomenda **artigos científicos de uma base curada** e se abstém
quando não há registro confiável. Projeto da disciplina de Inteligência Artificial (A3
Projeto Integrador, 40 pontos), de 10/10 a 05/12/2026.

- Sem LLM e sem serviço de IA pronto: o classificador de intenções e a recuperação são
  treinados/implementados pela equipe (requisito R3 do enunciado).
- Toda resposta aponta para um registro real da base, com DOI ou link verificado.
- Quando não há referência adequada, o bot **se abstém** em vez de inventar.

A especificação consolidada, com todas as decisões do documento unificado do projeto, está
em [`docs/especificacao.md`](docs/especificacao.md).

---

## Como rodar (só o que está aqui)

Requisitos: Python 3.11+ e uma venv. A coleta usa apenas APIs públicas, **sem chave**.

```bash
python -m venv venv
venv\Scripts\activate            # Windows
pip install -r requirements.txt
```

```bash
# 1) base curada (Marco 2) — a coleta demora; o resultado fica versionado em data/
python scripts/coleta/pipeline.py

# 2) classificador de intenções (Marco 4)
python scripts/treinar_classificador.py

# 3) API + interface (a própria API serve o web/)
uvicorn main:app --app-dir app --port 8000
```

Abra **<http://127.0.0.1:8000/>** — é o chat. A API também responde em `/saude`, `/chat`,
`/artigos`, `/periodicos`.

Testes e avaliação:

```bash
python -m pytest -q                # regras ABNT, contexto, recuperação, fluxo, coleta, dataset
python tests/avaliar.py            # métricas do Marco 5 sobre tests/casos_teste.csv
python tests/avaliar.py --md docs/avaliacao.md
node web/_verificar_interface.js                       # a interface desenha o chat
node web/_verificar_contrato.js http://127.0.0.1:8000  # a API real bate com o que o front lê
```

Diagnósticos (ajudam a explicar o comportamento na demonstração; ver
[`scripts/diagnostico/README.md`](scripts/diagnostico/README.md)):

```bash
python scripts/diagnostico/_verificar_api.py 8000        # as 11 perguntas simuladas
python scripts/diagnostico/_diag_recuperacao.py          # ranqueamento e recall
python scripts/diagnostico/_diag_match.py "clareamento dental" YouTube   # por que casou
```

Se a coleta ainda não rodou, a API sobe do mesmo jeito e responde `503`/abstenção
explicando o que falta — nenhum módulo quebra por base ausente.

---

## Endpoints

| Método | Rota | Uso |
|---|---|---|
| GET | `/` | a interface (chat) — servida pela própria API |
| GET | `/saude` | estado da base, do modelo e dos limiares |
| POST | `/chat` | fluxo completo com o traço da decisão |
| GET | `/artigos` | consulta direta à base (`?area=&ano=&limite=`) |
| GET | `/periodicos` | lista curada usada no parecer de fonte |
| POST | `/sessao/{id}/limpar` | limpa o contexto da conversa |

```bash
curl -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" \
     -d "{\"mensagem\": \"preciso de artigos sobre clareamento dental\", \"sessao\": \"demo\"}"
```

Contrato completo da interface: [`web/README.md`](web/README.md).

---

## Estado atual (11/10/2026)

| Item | Resultado |
|---|---|
| Base curada | 246 artigos · 107 periódicos · 100% CC-BY · 3 áreas |
| Dataset de intenções | 199 frases · 5 intenções (39–40 por intenção) |
| Testes automatizados | 83 passando (`python -m pytest -q`) |
| Acurácia de intenções | 1,000 (meta ≥ 0,85) |
| Precisão@5 da recuperação | 0,743 (meta ≥ 0,60) |
| Abstenção correta fora de escopo | 1,000 (meta ≥ 0,90) |
| Citações inventadas | 0 (meta = 0) |

Métricas medidas por `python tests/avaliar.py` sobre os 30 casos de
`tests/casos_teste.csv`; a análise das três falhas encontradas no caminho está em
[`docs/avaliacao.md`](docs/avaliacao.md).

---

## Arquitetura (Opção C — híbrida)

Um classificador de intenções treinado pela equipe decide o caminho; cada caminho responde
por recuperação ou por regras, e o bot nunca gera texto livre com referências.

```
pergunta
   │
   ├─ preprocessamento.py      minúsculas, acentos, stopwords (igual no treino e na inferência)
   ├─ intencoes.py             TF-IDF + Regressão Logística -> intenção + confiança
   │
   ├─ confiança < limiar ──────► abstencao.py
   │
   ├─ buscar_referencias ──────► recuperacao.py  (TF-IDF/cosseno + reordenação por curadoria)
   ├─ avaliar_fonte ───────────► periodicos.py   (lista curada; fora dela -> "não consta na base")
   ├─ formatar_referencia ─────► contexto.py + abnt.py (NBR 6023 por regras)
   ├─ orientar_busca ──────────► faq.py          (texto revisado da FAQ)
   └─ fora_de_escopo ──────────► abstencao.py    (+ encaminhamento ao orientador/biblioteca)
```

`fluxo.py` é o único ponto que aplica limiares e monta o **traço da decisão** (intenção,
confiança, ação, regra, score). Os limiares ficam todos em `app/config.py`.

### Estrutura do repositório

| Pasta | Conteúdo |
|---|---|
| `app/` | API e mecanismo de IA: `main.py`, `config.py`, `schemas.py`, `fluxo.py`, `preprocessamento.py`, `intencoes.py`, `recuperacao.py`, `abnt.py`, `periodicos.py`, `faq.py`, `contexto.py`, `abstencao.py` |
| `scripts/coleta/` | clientes e pipeline ETL: `config_coleta.py`, `comum.py`, `crossref.py`, `scielo.py`, `europepmc.py`, `doaj.py`, `medline.py`, `pipeline.py`, `_diag_cache.py` |
| `scripts/` | `treinar_classificador.py` |
| `scripts/diagnostico/` | scripts de apoio, não importados pelo sistema (`_verificar_api.py`, `_diag_recuperacao.py`, `_diag_match.py`, `_diag_cache.py`) |
| `data/` | `raw/` (cache), `knowledge_base.json`, `periodicos.json`, `faq_busca.json`, `intents.csv`, `casos_teste.csv`, `relatorio_coleta.md` |
| `models/` | `intencoes.joblib` |
| `tests/` | `casos_teste.csv`, `test_*.py`, `avaliar.py` |
| `docs/` | `especificacao.md`, `avaliacao.md`, `contribuicoes.md`, `fluxograma.md`, `pendencias.md` || `web/` | interface do chat: `index.html`, `app.js`, `estilo.css` (JavaScript local, sem CDN) |

---

## Base curada e critérios de curadoria

Fontes: **Crossref** (principal: busca, validação de DOI, enriquecimento), **SciELO
ArticleMeta**, **Europe PMC**, **DOAJ** (indexação e assunto do periódico, e busca de
artigos em Computação) e **NLM Catalog** (MEDLINE). Nenhuma exige chave de API; nada é
consultado em tempo de conversa.

Recorte: **2020–2026**, idiomas **pt/en**, licenças **CC-BY e CC0** (SA/NC/ND ficam de
fora), cota de **25 artigos por semente** e **100 por área**, em Computação, Odontologia e
Psicologia.

Um artigo entra na base quando: tem DOI, está no período, tem idioma e licença aceitos,
casa com uma semente temática, o DOI existe no Crossref, o periódico está indexado em
**DOAJ, SciELO ou MEDLINE** e a área confere pela LCC (DOAJ) ou pela área WoS (SciELO). O
funil de descartes por semente sai em `data/relatorio_coleta.md`.

Rodar uma área por vez (as saídas anteriores são preservadas):

```bash
python scripts/coleta/pipeline.py --area odontologia
```

> **Re-rodar é seguro.** Rodar de novo uma área **recoleta** essa área; se a recoleta não
> trouxer nada, a versão anterior da área é mantida (com aviso no console) em vez de ser
> apagada. O merge roda sem rede e tem teste de regressão em
> `tests/test_pipeline_coleta.py`.
>
 > Para inspecionar o cache antes de rodar: `python scripts/diagnostico/_diag_cache.py`.

### Estado da base

| Área | Artigos |
|---|---|
| Computação | 46 |
| Odontologia | 100 |
| Psicologia | 100 |
| **Total** | **246** (107 periódicos, 100% CC-BY) |

Computação fica abaixo da cota de 100: o Crossref, fonte principal, não sustenta essa área
no recorte temático (devolve domínios vizinhos) e o SciELO tem poucos periódicos de
Computação. A lacuna foi reduzida com o `Article Search` do DOAJ como fonte complementar de
artigos dessa área — a decisão está registrada em
[`docs/especificacao.md`](docs/especificacao.md) e deve ser confirmada no Marco 3.

---

## O que o bot faz e o que não faz

**Faz:** recomenda até 5 artigos com ano, periódico, DOI e o motivo da indicação; dá parecer
sobre um periódico pela lista curada; monta a referência ABNT (NBR 6023) de um artigo já
indicado ("o segundo artigo"); orienta a busca no SciELO, Google Acadêmico, PubMed, DOAJ e
CAPES; abstenção com encaminhamento quando a pergunta sai do escopo.

**Não faz (fora de escopo declarado):** resumir ou gerar o texto do TCC, orientação clínica
ou terapêutica, busca em bases externas durante a conversa, login/histórico por usuário,
garantia de adequação ao tema.

---

## Restrições do projeto (respeitadas no código)

- Python e ferramentas gratuitas/locais; nenhum serviço de IA pronto.
- Nenhum dado pessoal real; nenhuma chave de API no repositório.
- A coleta usa APIs públicas **apenas de leitura** e roda fora do chatbot.
- Sem LLM em nenhum ponto do fluxo de resposta.
- Uso de IA generativa declarado: ver [`docs/contribuicoes.md`](docs/contribuicoes.md).

---

## Pendências humanas do TAP

1. Distribuir os quatro papéis entre os integrantes (o TAP ainda diz "a definir").
2. Colher as assinaturas de aprovação do TAP (professor e gerente).
3. Avisar o professor que a coleta usa APIs públicas só de leitura, fora do chatbot.

As pendências técnicas do documento unificado (xylose no `requirements.txt`, atributos do
xylose, filtro de data do ArticleMeta, `faq_busca.json` e `intents.csv`) estão resolvidas —
o quadro de situação está no fim de [`docs/especificacao.md`](docs/especificacao.md). A
lista completa do que segue aberto está em
[`docs/pendencias.md`](docs/pendencias.md).

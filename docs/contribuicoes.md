# Registro de contribuições — Artikel

Atualizado em 11/10/2026. O documento do projeto exige, no requisito R7, "base versionada
sem chave de API, scripts de coleta e testes, registro de contribuições". Este arquivo é
esse registro.

## Papéis do TAP

| Papel | Responsabilidade verificável | Integrante |
|---|---|---|
| Levantamento e base | Script de coleta, curadoria, lista de periódicos, FAQ e licenças | A definir (TAP) |
| Implementação e integração | Classificador, recuperação, regras ABNT e fluxo | A definir (TAP) |
| Dados e testes | Dataset de intenções, 30 casos, métricas e análise de erros | A definir (TAP) |
| Interface, documentação e validação | Interface, README, relatório e roteiro da demonstração | A definir (TAP) |

> **Pendência 1 do documento:** os quatro papéis ainda não foram distribuídos. Preencher a
> coluna "Integrante" é pré-requisito do Marco 4 (a entrega exige o registro de
> contribuições por pessoa, não só o total do grupo).

## Como registrar a contribuição

Cada integrante registra o que fez **no próprio commit**, com prefixo convencional:

| Prefixo | Uso |
|---|---|
| `feat:` | funcionalidade nova |
| `fix:` | correção |
| `data:` | base, cache de coleta, lista de periódicos, FAQ, dataset |
| `docs:` | README, relatório, especificação |
| `test:` | casos de teste e métricas |
| `config:` | limiares, dependências, ambiente |

Exemplo: `data: coleta de odontologia com 100 artigos curados (Miguel)`.

## Entregas por marco

| Marco | Entrega | Onde está no repositório | Situação |
|---|---|---|---|
| 1 — Problema | TAP, persona, 5 dores, objetivo, limites, perguntas simuladas | `docs/especificacao.md` (seções 1–4, 9) | consolidado |
| 2 — Dados | Base, lista de periódicos e FAQ versionadas; origem, licença e critérios | `data/knowledge_base.json`, `data/periodicos.json`, `data/faq_busca.json`, `data/relatorio_coleta.md`, `scripts/coleta/` | implementado |
| 3 — Técnica | Arquitetura justificada, comparação com a Opção D, fluxograma e limiares | `docs/especificacao.md` (seção 6), `app/config.py`, `docs/fluxograma.png` | limiares provisórios (revisão no Marco 3) |
| 4 — Protótipo | Código executável, interface, README e registro de contribuições | `app/`, `web/`, `README.md`, este arquivo | implementado |
| 5 — Avaliação | Planilha de 30 testes, métricas, análise de 3 falhas e melhorias | `tests/casos_teste.csv`, `tests/avaliar.py`, `docs/avaliacao.md` | métricas prontas; análise de falhas a escrever |
| 6 — Defesa | Relatório de 6+ páginas, repositório/ZIP e demonstração de 8 minutos | relatório (a escrever), `README.md` | pendente |

## Declaração de uso de IA generativa

O enunciado exige declarar o uso de IA generativa. Preencher antes da entrega:

| Item | Descrição |
|---|---|
| Ferramenta usada | _(a preencher)_ |
| Para quê | _(ex.: revisão de texto do relatório, apoio na estruturação dos módulos)_ |
| O que **não** foi feito com IA | A coleta, o treino do classificador e a recuperação usam código e dados próprios; nenhuma resposta do bot é gerada por LLM em tempo de execução |
| Revisão humana | Todo conteúdo gerado com apoio de IA foi revisado por um integrante antes de entrar no repositório |

## Pendências com dono

| # | Pendência | Dono | Marco |
|---|---|---|---|
| 1 | Distribuir os quatro papéis entre os integrantes | equipe | 2 |
| 2 | Colher assinaturas de aprovação do TAP (professor e gerente) | gerente | 2 |
| 3 | Avisar o professor que a coleta usa APIs públicas só de leitura | equipe | 2 |
| 4 | Revisar os limiares de confiança e de score | implementação | 3 |
| 5 | Analisar as 3 falhas do classificador e propor melhorias | dados e testes | 5 |
| 6 | Escrever o relatório de 6+ páginas e o roteiro da demonstração | interface e documentação | 6 |
| 7 | Desenhar o fluxograma (`docs/fluxograma.png`) | implementação | 3 |

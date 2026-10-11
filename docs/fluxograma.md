# Fluxograma do Artikel (Opção C — híbrida)

O documento do projeto pede, no Marco 3, "arquitetura justificada, comparação com a Opção D,
fluxograma e limiares". Este arquivo é a fonte do fluxograma; `docs/fluxograma.png` deve ser
gerado a partir dele para o relatório.

## Decisão da pergunta

```mermaid
flowchart TD
    A[Pergunta do usuário] --> B[preprocessamento.py<br/>minúsculas, acentos, stopwords]
    B --> C[intencoes.py<br/>TF-IDF + Regressão Logística]
    C --> D{confiança ≥ LIMIAR_CONFIANCA?}
    D -- não --> Z1[abstencao.py<br/>pede para reformular]
    D -- sim --> E{qual intenção?}

    E -- buscar_referencias --> F[recuperacao.py<br/>cosseno sobre título+resumo+palavras-chave]
    F --> G{cobertura temática<br/>≥ COBERTURA_MINIMA?}
    G -- não --> Z2[abstencao.py<br/>nenhum registro do tema]
    G -- sim --> H[reordenação por curadoria<br/>revisão por pares, indexação, ano, área]
    H --> I{score ≥ LIMIAR_SCORE?}
    I -- não --> Z2
    I -- sim --> J[contexto.py guarda a lista<br/>resposta com 3 a 5 artigos + motivo]

    E -- avaliar_fonte --> K[periodicos.py<br/>lista curada]
    K --> L{consta na base?}
    L -- não --> M["não consta na base"<br/>+ como verificar no DOAJ/SciELO/MEDLINE]
    L -- sim --> N[parecer: indexação, revisão, licença]

    E -- formatar_referencia --> O{contexto.py<br/>resolve o artigo citado?}
    O -- não --> Z3[abstencao.py<br/>precisa de uma busca antes]
    O -- sim --> P[abnt.py<br/>referência NBR 6023 por regras]

    E -- orientar_busca --> Q[faq.py<br/>entrada mais próxima]
    Q --> R{score mínimo da FAQ?}
    R -- não --> Z4[abstencao.py<br/>pergunta fora do roteiro da FAQ]
    R -- sim --> S[resposta da FAQ revisada + passos]

    E -- fora_de_escopo --> Z5[abstencao.py<br/>mensagem curta e, após repetições,<br/>encaminhamento ao orientador/biblioteca]

    J --> T[resposta + traço da decisão]
    M --> T
    N --> T
    P --> T
    S --> T
    Z1 --> T
    Z2 --> T
    Z3 --> T
    Z4 --> T
    Z5 --> T
```

Todo caminho termina em `fluxo.py`, que monta a resposta **e** o traço da decisão (intenção,
confiança, ação, regra aplicada, número de candidatos, score máximo e se o contexto foi
usado). É esse traço que a interface mostra no painel recolhível e que serve de evidência do
requisito R4 na demonstração.

## Pipeline de coleta (Marco 2)

```mermaid
flowchart LR
    A[Sementes por área] --> B[Crossref pt/en]
    A --> C[SciELO ArticleMeta]
    A --> D[Europe PMC]
    B --> E[Filtro básico<br/>DOI, período, idioma, licença]
    C --> E
    D --> E
    E --> F[Filtro temático<br/>radical de 5 caracteres]
    F --> G[Dedup por DOI + mescla entre fontes]
    G --> H[Validação e enriquecimento no Crossref]
    H --> I[Refiltro básico]
    I --> J{Indexado em DOAJ,<br/>SciELO ou MEDLINE?}
    J -- não --> X[Descartado e contado no funil]
    J -- sim --> K{Área confere<br/>LCC ou área WoS?}
    K -- não --> X
    K -- sim --> L[Cota: 25 por semente, 100 por área]
    L --> M[knowledge_base.json<br/>periodicos.json<br/>relatorio_coleta.md]
    N[DOAJ] --> J
    O[NLM Catalog] --> J
```

## Comparação com a Opção D (LLM + recuperação)

| Critério | Opção C (escolhida) | Opção D (LLM + recuperação) |
|---|---|---|
| Risco de citação inventada | Zero: a resposta só exibe texto da base curada | Alto: o modelo pode inventar referência plausível |
| Cumpre R3 ("IA implementada pela equipe") | Sim: classificador e recuperação são da equipe | Sozinha, não: o mecanismo passa a ser o serviço externo |
| Custo e dependência | Só bibliotecas locais e gratuitas | Serviço externo, latência e possível chave de API |
| Explicabilidade | Alta: cada resposta traz o traço da decisão e o motivo de cada artigo | Baixa: a decisão fica dentro do modelo |
| Qualidade do texto | Rígida e previsível (é o aceitável para o escopo) | Mais fluida |
| Aderência às restrições do projeto | Total (sem chave de API, sem dado pessoal) | Exige aprovação do professor e declarar uso de IA |

A Opção C foi mantida porque o diferencial do Artikel é justamente **não** inventar
referência; o texto mais fluido da Opção D não compensa reintroduzir o risco que o projeto
existe para eliminar.

## Limiares (revisão prevista para o Marco 3)

| Limiar | Onde | Valor atual | Como foi escolhido |
|---|---|---|---|
| `LIMIAR_CONFIANCA` | `app/config.py` | 0,35 | Abaixo disso a probabilidade do classificador não se distingue entre intenções |
| `LIMIAR_SCORE` | `app/config.py` | 0,10 | Piso de similaridade para recomendar |
| `COBERTURA_MINIMA` | `app/config.py` | 0,34 | Exige ao menos um termo de conteúdo da pergunta no artigo |
| `TOP_K` | `app/config.py` | 5 | "Top 3–5 artigos" do documento |
| Bônus de curadoria | `app/config.py` | 0,02–0,06 | Pequenos de propósito: desempatam, não substituem relevância |

Os valores devem ser revistos com a distribuição de scores de `tests/avaliar.py` no Marco 3,
como o próprio documento prevê (pendência 8).

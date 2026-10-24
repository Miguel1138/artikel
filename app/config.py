"""Limiares, pesos e caminhos do Artikel.

Tudo que é ajustável fica aqui (requisito R4: `fluxo.py` não decide nada por conta
própria). Os valores marcados com [Marco 3] são provisórios e devem ser revistos quando
a avaliação do Marco 5 rodar.
"""
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

# --- Dados -------------------------------------------------------------
DIR_DATA = RAIZ / "data"
DIR_MODELS = RAIZ / "models"
DIR_DOCS = RAIZ / "docs"
DIR_WEB = RAIZ / "web"
ARQ_BASE = DIR_DATA / "knowledge_base.json"
ARQ_PERIODICOS = DIR_DATA / "periodicos.json"
ARQ_FAQ = DIR_DATA / "faq_busca.json"
ARQ_GLOSSARIO = DIR_DATA / "glossario_pt_en.json"   # gerado por scripts/gerar_glossario.py
ARQ_INTENTS = DIR_DATA / "intents.csv"
ARQ_MODELO = DIR_MODELS / "intencoes.joblib"
ARQ_ENCODER = DIR_MODELS / "encoder"            # ONNX baixado por scripts/baixar_encoder.py
ARQ_CASOS = RAIZ / "tests" / "casos_teste.csv"

# Recorte da base curada, espelhado de `scripts/coleta/config_coleta.py`. Fica duplicado de
# propósito: a API não importa nada dos scripts de coleta (coleta isolada de app/, seção 8
# do documento). Se o recorte mudar, mude nos dois lugares.
ANO_INICIO, ANO_FIM = 2020, 2026

# --- Intenções ---------------------------------------------------------
# A ordem define a legenda da matriz de confusão.
INTENCOES = [
    "buscar_referencias",
    "avaliar_fonte",
    "formatar_referencia",
    "orientar_busca",
    "fora_de_escopo",
]
FORA_DE_ESCOPO = "fora_de_escopo"

# Probabilidade mínima do classificador para aceitar a intenção prevista (>=: abaixo disso
# o bot se abstém). Medido FORA da amostra com o modelo de votação (n-gramas + encoder), 0,60
# aceita ~88% das perguntas com ~98% de precisão. 0,80 aceitava 72% e, em perguntas de tema
# novo, abstinha de quase toda busca legítima (curva em docs/pendencias.md).
LIMIAR_CONFIANCA = 0.60
# Faixa de esclarecimento: entre este valor e LIMIAR_CONFIANCA o bot não se abstém de cara,
# pergunta "você quer X?" e só age depois do "sim". Abaixo dele, abstenção como antes.
# 0,35 cobre as perguntas legítimas que ficavam em 0,38–0,57 (tema novo, "e a do terceiro").
LIMIAR_ESCLARECIMENTO = 0.35
# Uma segunda intenção entra como alternativa na pergunta se tiver pelo menos esta probabilidade
# ("palavras-chave para achar artigos": buscar 0,55 / orientar 0,43 -> pergunta qual dos dois).
MIN_SEGUNDA_OPCAO = 0.25
# Fora de escopo previsto nunca vira pergunta, mesmo com uma ação logo atrás: "escreve sobre
# depressão" sai 0,51 fora de escopo contra 0,48 busca, e oferecer busca ali enfraquece a
# abstenção de pedidos de escrita (tests/test_esclarecimento.py).
# [Marco 3] similaridade de cosseno mínima para recomendar um artigo.
LIMIAR_SCORE = 0.10
# Fração mínima dos termos de conteúdo da pergunta que precisam aparecer no artigo.
# Sem isso, a pergunta "artigos sobre astrofísica de neutrinos" casa com um artigo de
# odontologia só porque ambos compartilham palavras genéricas ("artigos").
#
# Valor escolhido com dados, não por intuição:
# `scripts/diagnostico/_diag_limiar_cobertura.py` compara 10 perguntas que devem achar
# artigo com 6 fora do recorte. Em 0,34 e 0,5 duas perguntas fora do tema ainda devolviam
# artigo ("física quântica" casava com "saúde física" num artigo de Psicologia; "direito
# penal" com "penal" noutro). Em 0,6 nenhuma passa e nenhuma pergunta legítima fica sem
# resposta.
COBERTURA_MINIMA = 0.60
# Com pelo menos este número de artigos que cobrem TODOS os termos da pergunta, os de
# cobertura parcial (>= COBERTURA_MINIMA) ficam de fora; sem isso eles só preenchem a lista.
MIN_COBERTURA_COMPLETA = 3
# --- Tema solto ("depressão", sem verbo): ver Motor.so_tema e o passo correspondente de fluxo.py
# Um termo só é tema da base se aparece em pelo menos tantos artigos; menções únicas são
# incidentais ("faz", "psicólogo" aparecem em um artigo cada).
MIN_ARTIGOS_TEMA = 2
# No máximo tantas palavras de conteúdo para a mensagem contar como "só um tema".
MAX_TERMOS_TEMA = 4
# Palavras que pertencem a OUTRAS ações do bot (bases e portais, tarefas de escrita) e nunca
# contam como tema, mesmo que apareçam na base: "scielo" é avaliar fonte, "pubmed" é orientar
# busca, "introdução" é pedido de escrita. Sem eles uma palavra solta do sistema viraria busca.
TERMOS_DO_SISTEMA = frozenset({
    "scielo", "pubmed", "capes", "doaj", "medline", "lilacs", "scopus", "crossref", "google",
    "scholar", "academico", "qualis", "portal", "wikipedia", "abnt", "nbr", "doi", "issn",
    "preprint", "preprints", "journal", "periodico", "periodicos", "revista", "revistas",
    "indexacao", "predatoria", "predatorio", "impacto",
    "introducao", "conclusao", "metodologia", "capitulo", "redacao", "paragrafo", "resumo",
    "apresentacao", "slides", "cronograma", "fichamento", "tradução", "traducao",
})
# Quantos artigos a resposta de busca devolve (documento: top 3–5).
TOP_K = 5
# Artigos usados para calcular a Precisão@5 na avaliação.
K_PRECISAO = 5

# Quantas perguntas seguidas fora de escopo antes de repetir o encaminhamento completo.
ABSTENCOES_ANTES_DE_REPETIR = 3

# --- Reordenação por curadoria (requisito R3) --------------------------
# O score final é `similaridade + bônus`, limitado a 1. Bônus pequenos: eles desempatam
# artigos parecidos, não substituem a relevância temática.
BONUS_REVISAO = {"dupla_cega": 0.06, "pares": 0.04, "editorial": 0.0, None: 0.0}
BONUS_INDEXACAO = {"DOAJ": 0.03, "SciELO": 0.03, "MEDLINE": 0.02}
BONUS_INDEXACAO_MAX = 0.05
BONUS_ANO_RECENTE = 0.03          # artigos dos últimos 2 anos do recorte
BONUS_MESMA_AREA = 0.02           # quando a pergunta cita uma das três áreas

# --- Modelo ------------------------------------------------------------
# TF-IDF + Regressão Logística é o padrão do documento; Naive Bayes é a alternativa.
CLASSIFICADOR = "logistica"        # "logistica" | "bayes"
# Representação do texto das intenções (ver `preprocessador_generico.criar_vetorizador`).
# Bag of Words não é melhor que TF-IDF aqui: a comparação está em
# `scripts/diagnostico/_diag_vetorizador.py`. Mudou? Rode `treinar_classificador.py` de novo.
VETORIZADOR = "tfidf"              # "tfidf" | "bow" | "bow_binario"
NGRAMAS = (1, 3)                   # (1, 3) conta também pares e trios de palavras vizinhas
NGRAMAS_CARACTERES = (2, 5)        # letras dentro da palavra: robusto a flexão e digitação; None desliga
REMOVER_STOPWORDS_INTENCAO = False # "como", "que", "para" carregam a intenção (ver normalizar_intencao)
C_LOGISTICA = 50.0                 # regularização fraca: probabilidades mais nítidas
# Ramo semântico (encoder de sentenças local, ver app/encoder.py). A decisão final é a média
# ponderada dos dois ramos: PESO_NGRAMAS para o lexical e o resto para o semântico.
# 0,7/0,3 foi o ponto em que o teste oficial não piora e as paráfrases novas melhoram.
USAR_ENCODER = True
PESO_NGRAMAS = 0.7
C_ENCODER = 100.0
SEED = 42
TESTE_FRACAO = 0.25                # holdout interno do treino (o teste real é casos_teste.csv)

# --- API ---------------------------------------------------------------
TITULO_API = "Artikel API"
VERSAO_API = "0.1.0"

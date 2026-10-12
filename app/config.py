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

# [Marco 3] probabilidade mínima do classificador para aceitar a intenção prevista.
LIMIAR_CONFIANCA = 0.35
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
NGRAMAS = (1, 2)                   # (1, 2) conta também pares de palavras vizinhas
SEED = 42
TESTE_FRACAO = 0.25                # holdout interno do treino (o teste real é casos_teste.csv)

# --- API ---------------------------------------------------------------
TITULO_API = "Artikel API"
VERSAO_API = "0.1.0"

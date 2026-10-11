"""Classificador de intenções próprio (requisito R3).

TF-IDF + Regressão Logística treinados pela equipe sobre `data/intents.csv`. Sem LLM e
sem serviço pronto: o modelo e o vetorizador são gravados em `models/intencoes.joblib`.

Naive Bayes é a alternativa prevista no documento; troque em `app/config.py`.
"""
from __future__ import annotations

import sys
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.naive_bayes import MultinomialNB

# app/ não é pacote instalável: o script roda da raiz do repositório.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from config import ARQ_INTENTS, ARQ_MODELO, CLASSIFICADOR, SEED, TESTE_FRACAO, VERSAO_API
from preprocessamento import normalizar


def carregar_dataset(caminho: Path = ARQ_INTENTS) -> tuple[list[str], list[str]]:
    """Lê intents.csv sem pandas, para o treino depender só de scikit-learn."""
    import csv

    frases, rotulos = [], []
    with caminho.open(encoding="utf-8", newline="") as fh:
        for linha in csv.DictReader(fh):
            texto = (linha.get("frase") or "").strip()
            intencao = (linha.get("intencao") or "").strip()
            if texto and intencao:
                frases.append(texto)
                rotulos.append(intencao)
    return frases, rotulos


def construir_modelo():
    if CLASSIFICADOR == "bayes":
        return MultinomialNB(alpha=0.3)
    return LogisticRegression(max_iter=2000, C=8.0, class_weight="balanced", random_state=SEED)


def treinar(salvar: bool = True) -> dict:
    frases, rotulos = carregar_dataset()
    if len(set(rotulos)) < 2:
        raise SystemExit("data/intents.csv precisa de pelo menos duas intenções.")

    vetorizador = TfidfVectorizer(
        preprocessor=normalizar,          # mesmo pré-processamento do treino e da inferência
        ngram_range=(1, 2),
        sublinear_tf=True,
        min_df=1,
    )
    X = vetorizador.fit_transform(frases)

    # Holdout interno: serve para avisar cedo se o dataset piorar. A avaliação oficial é
    # tests/avaliar.py com casos_teste.csv, que nunca entram no treino.
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, rotulos, test_size=TESTE_FRACAO, random_state=SEED, stratify=rotulos
    )
    avaliacao = construir_modelo()
    avaliacao.fit(X_tr, y_tr)
    acuracia_holdout = float(avaliacao.score(X_te, y_te))

    modelo = construir_modelo()
    modelo.fit(X, rotulos)
    cv = cross_val_score(construir_modelo(), X, rotulos, cv=4)

    pacote = {
        "vetorizador": vetorizador,
        "modelo": modelo,
        "intencoes": sorted(set(rotulos)),
        "versao": VERSAO_API,
        "treinado_com": len(frases),
    }
    if salvar:
        ARQ_MODELO.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(pacote, ARQ_MODELO)

    print(f"frases: {len(frases)} | intenções: {len(pacote['intencoes'])} | classificador: {CLASSIFICADOR}")
    print(f"holdout {1 - TESTE_FRACAO:.0%}/{TESTE_FRACAO:.0%}: acurácia {acuracia_holdout:.3f}")
    print(f"validação cruzada (4 partições): {cv.mean():.3f} ± {cv.std():.3f}")
    if salvar:
        print(f"modelo gravado em {ARQ_MODELO.relative_to(ARQ_MODELO.parents[1])}")
    return pacote


if __name__ == "__main__":
    treinar()

"""Classificador de intenções próprio (requisito R3).

Votação entre dois ramos treinados pela equipe sobre `data/intents.csv`: (1) TF-IDF de palavras e
caracteres + Regressão Logística e (2) vetores de um encoder de sentenças LOCAL + Regressão
Logística. Sem LLM, sem API e sem serviço remoto: o encoder só produz vetores, roda em CPU
sem rede, e a decisão é da regressão da equipe. Tudo é gravado em `models/intencoes.joblib`.

Naive Bayes é a alternativa prevista no documento; troque em `app/config.py`, onde também
se escolhe o vetorizador (`tfidf`, `bow` ou `bow_binario`) e os n-gramas.
"""
from __future__ import annotations

import sys
from pathlib import Path

import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import make_pipeline

# app/ não é pacote instalável: o script roda da raiz do repositório.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from config import (ARQ_INTENTS, ARQ_MODELO, C_ENCODER, C_LOGISTICA, CLASSIFICADOR, NGRAMAS,
                    NGRAMAS_CARACTERES, PESO_NGRAMAS, REMOVER_STOPWORDS_INTENCAO, SEED,
                    TESTE_FRACAO, USAR_ENCODER, VERSAO_API, VETORIZADOR)
from encoder import VetorizadorSemantico, encoder_disponivel
from preprocessador_generico import criar_vetorizador
from votacao import Votacao
from preprocessamento import normalizar, normalizar_intencao


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
    return LogisticRegression(max_iter=3000, C=C_LOGISTICA, class_weight="balanced", random_state=SEED)


def construir_vetorizador():
    """Vetorizador das intenções. O pré-processador vai DENTRO dele e é gravado no .joblib:
    a inferência só chama `transform(texto_bruto)`, então treino e uso nunca divergem."""
    return criar_vetorizador(
        VETORIZADOR,
        normalizar if REMOVER_STOPWORDS_INTENCAO else normalizar_intencao,
        ngramas=NGRAMAS,
        caracteres=NGRAMAS_CARACTERES,
    )


def construir_classificador():
    """Votação entre o ramo de n-gramas e o ramo semântico (encoder local).

    Recebe e devolve texto bruto: o pré-processamento mora dentro de cada ramo. Sem encoder
    (ou com Naive Bayes, que não aceita vetores negativos) fica só o ramo de n-gramas.
    """
    ngramas = make_pipeline(construir_vetorizador(), construir_modelo())
    if not USAR_ENCODER or CLASSIFICADOR == "bayes":
        return ngramas
    if not encoder_disponivel():
        raise SystemExit("USAR_ENCODER=True, mas o encoder não está em models/encoder/.\n"
                         "Rode: python scripts/baixar_encoder.py  (ou USAR_ENCODER=False em app/config.py)")
    semantico = make_pipeline(
        VetorizadorSemantico(),
        LogisticRegression(max_iter=3000, C=C_ENCODER, class_weight="balanced", random_state=SEED),
    )
    return Votacao([("ngramas", ngramas, PESO_NGRAMAS), ("encoder", semantico, 1 - PESO_NGRAMAS)])


def treinar(salvar: bool = True) -> dict:
    frases, rotulos = carregar_dataset()
    if len(set(rotulos)) < 2:
        raise SystemExit("data/intents.csv precisa de pelo menos duas intenções.")

    # Holdout interno: serve para avisar cedo se o dataset piorar. A avaliação oficial é
    # tests/avaliar.py com casos_teste.csv, que nunca entram no treino.
    f_tr, f_te, y_tr, y_te = train_test_split(
        frases, rotulos, test_size=TESTE_FRACAO, random_state=SEED, stratify=rotulos
    )
    acuracia_holdout = float(construir_classificador().fit(f_tr, y_tr).score(f_te, y_te))

    modelo = construir_classificador().fit(frases, rotulos)
    cv = cross_val_score(construir_classificador(), frases, rotulos, cv=4)

    pacote = {
        "modelo": modelo,           # recebe texto bruto: predict_proba([frase])
        "intencoes": sorted(set(rotulos)),
        "versao": VERSAO_API,
        "treinado_com": len(frases),
        "ramos": [r[0] for r in getattr(modelo, "ramos", [("ngramas",)])],
    }
    if salvar:
        ARQ_MODELO.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(pacote, ARQ_MODELO)

    print(f"frases: {len(frases)} | intenções: {len(pacote['intencoes'])} | classificador: {CLASSIFICADOR} "
          f"| ramos: {', '.join(pacote['ramos'])} | ngramas: palavras{NGRAMAS} + caracteres{NGRAMAS_CARACTERES}")
    print(f"holdout {1 - TESTE_FRACAO:.0%}/{TESTE_FRACAO:.0%}: acurácia {acuracia_holdout:.3f}")
    print(f"validação cruzada (4 partições): {cv.mean():.3f} ± {cv.std():.3f}")
    if salvar:
        print(f"modelo gravado em {ARQ_MODELO.relative_to(ARQ_MODELO.parents[1])}")
    return pacote


if __name__ == "__main__":
    treinar()

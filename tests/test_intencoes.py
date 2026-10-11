"""Testes do classificador de intenções (R3, objetivo específico 2).

Verificam o dataset (`data/intents.csv`), a integridade do modelo gravado e o piso de
qualidade exigido pelo documento: acurácia ≥ 85% com validação cruzada.

Os casos de `tests/casos_teste.csv` **nunca** entram no treino; o teste abaixo confere
apenas o holdout interno do dataset de treino.
"""
import csv
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "app"))
sys.path.insert(0, str(RAIZ / "scripts"))

from config import ARQ_INTENTS, ARQ_MODELO, INTENCOES  # noqa: E402


def ler_intents():
    with ARQ_INTENTS.open(encoding="utf-8", newline="") as fh:
        return [l for l in csv.DictReader(fh) if l.get("frase")]


def test_dataset_tem_as_cinco_intencoes():
    linhas = ler_intents()
    assert {l["intencao"] for l in linhas} == set(INTENCOES)


def test_dataset_tem_20_a_40_frases_por_intencao():
    """O documento pede 20–40 frases por intenção (risco 'poucos exemplos')."""
    linhas = ler_intents()
    for intencao in INTENCOES:
        n = sum(1 for l in linhas if l["intencao"] == intencao)
        assert 20 <= n <= 40, f"{intencao}: {n} frases"


def test_frases_sem_duplicata():
    frases = [l["frase"].strip().lower() for l in ler_intents()]
    assert len(frases) == len(set(frases))


def test_frases_do_teste_nao_estao_no_treino():
    """Frase de teste no treino inflaria a acurácia do Marco 5.

    O caso 3 é a pergunta simulada do Marco 1 e por isso é o único que se aproxima de uma
    frase de treino; o treino tem variantes ("referência do primeiro item da lista"), nunca
    a frase idêntica. Este teste é o que garante que continua assim.
    """
    treino = {l["frase"].strip().lower() for l in ler_intents()}
    caminho = RAIZ / "tests" / "casos_teste.csv"
    with caminho.open(encoding="utf-8", newline="") as fh:
        for linha in csv.DictReader(fh):
            pergunta = (linha.get("pergunta") or "").strip().lower()
            if pergunta:
                assert pergunta not in treino, f"caso de teste no treino: {pergunta}"


def test_modelo_gravado_carrega_e_responde():
    if not ARQ_MODELO.exists():
        pytest.skip("modelo ausente; rode python scripts/treinar_classificador.py")
    from intencoes import Classificador

    clf = Classificador()
    assert clf.carregado, clf.erro
    intencao, confianca = clf.prever("preciso de artigos sobre clareamento dental")
    assert intencao == "buscar_referencias"
    assert 0.0 <= confianca <= 1.0


def test_acuracia_minima_de_validacao_cruzada():
    """Piso de 85% do documento, medido em 4 partições sobre o dataset de treino."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import cross_val_score

    from preprocessamento import normalizar

    linhas = ler_intents()
    frases = [l["frase"] for l in linhas]
    rotulos = [l["intencao"] for l in linhas]
    vetor = TfidfVectorizer(preprocessor=normalizar, ngram_range=(1, 2), sublinear_tf=True)
    X = vetor.fit_transform(frases)
    modelo = LogisticRegression(max_iter=2000, C=8.0, class_weight="balanced", random_state=42)
    notas = cross_val_score(modelo, X, rotulos, cv=4)
    assert notas.mean() >= 0.85, f"acurácia de validação cruzada: {notas.mean():.3f}"

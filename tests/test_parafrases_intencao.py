"""Generalização do classificador de intenções em frases NOVAS (fora do treino e do teste).

`tests/parafrases_intencao.csv` tem 40 paráfrases das cinco intenções com vocabulário que
não está em `data/intents.csv`. É o teste que responde "o modelo entende a frase ou só
decora palavras?" sem precisar ampliar o CSV a cada pergunta nova.
"""
import csv
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "app"))

from config import ARQ_INTENTS, ARQ_MODELO, LIMIAR_CONFIANCA  # noqa: E402

ARQ = RAIZ / "tests" / "parafrases_intencao.csv"


def ler(caminho, col):
    with caminho.open(encoding="utf-8", newline="") as fh:
        return [(l[col].strip(), l["intencao"].strip()) for l in csv.DictReader(fh) if l.get(col)]


def test_parafrases_nao_estao_no_treino_nem_nos_casos_de_teste():
    usadas = {f.lower() for f, _ in ler(ARQ_INTENTS, "frase")}
    usadas |= {l["pergunta"].strip().lower() for l in csv.DictReader((RAIZ / "tests" / "casos_teste.csv").open(encoding="utf-8", newline="")) if l.get("pergunta")}
    repetidas = [f for f, _ in ler(ARQ, "frase") if f.lower() in usadas]
    assert not repetidas, repetidas


def test_acuracia_em_parafrases_novas():
    if not ARQ_MODELO.exists():
        pytest.skip("modelo ausente; rode python scripts/treinar_classificador.py")
    from intencoes import Classificador

    clf = Classificador()
    casos = ler(ARQ, "frase")
    certas = aceitas = 0
    for frase, esperada in casos:
        prevista, confianca = clf.prever(frase)
        certas += prevista == esperada
        aceitas += prevista == esperada and confianca >= LIMIAR_CONFIANCA
    # medido: n-gramas sozinhos 36/40 (31 aceitas); com o encoder 37/40 (35 aceitas)
    assert certas / len(casos) >= 0.85, f"{certas}/{len(casos)} corretas"
    assert aceitas / len(casos) >= 0.75, f"{aceitas}/{len(casos)} corretas E aceitas no limiar {LIMIAR_CONFIANCA}"

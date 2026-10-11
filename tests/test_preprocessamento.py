"""Testes do pré-processamento compartilhado (treino e inferência)."""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "app"))

import preprocessamento as pp  # noqa: E402


def test_sem_acento():
    assert pp.sem_acento("referência científica") == "referencia cientifica"


def test_tokenizar_remove_pontuacao():
    assert pp.tokenizar("Preciso de artigos, sobre cárie infantil?") == \
        ["preciso", "de", "artigos", "sobre", "carie", "infantil"]


def test_normalizar_remove_stopwords():
    assert pp.normalizar("Preciso de artigos sobre cárie") == "preciso artigos carie"


def test_normalizar_mesmo_texto_nos_dois_lados():
    """O ponto crítico do R3: treino e inferência usam exatamente a mesma função."""
    frase = "Como procuro artigos no SciELO?"
    assert pp.normalizar(frase) == pp.normalizar("  como procuro   artigos no scielo  ")


def test_radical_preserva_palavras_nucleares():
    assert pp.radical("artigos") == "artigos"      # nuclear: não corta
    assert pp.radical("referencias") == "referencia"
    assert pp.radical("dental") == "dental"        # curta demais para cortar


def test_termos_relevantes_usa_radical():
    termos = pp.termos_relevantes("artigos sobre ansiedade em universitários")
    assert "ansiedade" in termos
    assert "artigos" in termos
    assert "sobre" not in termos and "em" not in termos


def test_texto_vazio():
    assert pp.tokenizar("") == []
    assert pp.normalizar(None) == ""

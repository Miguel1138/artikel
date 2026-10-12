"""Testes do encoder de sentenças local e da votação (pulam se o modelo não foi baixado)."""
import io
import sys
from pathlib import Path

import numpy as np
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "app"))

import encoder  # noqa: E402

pytestmark = pytest.mark.skipif(
    not encoder.encoder_disponivel(),
    reason="encoder ausente; rode: python scripts/baixar_encoder.py",
)


def test_vetores_tem_384_dimensoes_e_norma_1():
    v = encoder.obter_encoder().codificar(["artigos sobre cárie", "como formato a referência?"])
    assert v.shape == (2, 384)
    assert np.allclose(np.linalg.norm(v, axis=1), 1.0, atol=1e-5)


def test_parafrase_fica_mais_perto_que_assunto_diferente():
    """É isso que o TF-IDF não faz: aproximar frases sem palavras em comum."""
    e = encoder.obter_encoder()
    a, b, c = e.codificar([
        "relação entre pais e filhos",
        "artigos sobre a convivência de pais e filhos",
        "como formatar uma referência em ABNT",
    ])
    assert a @ b > 0.6 and a @ b > a @ c + 0.3


def test_mesma_frase_da_o_mesmo_vetor_em_lotes_diferentes():
    e = encoder.obter_encoder()
    sozinha = e.codificar(["qualidade do sono em estudantes"])[0]
    em_lote = e.codificar(["outra frase bem mais longa para forçar preenchimento de tokens", "qualidade do sono em estudantes"])[1]
    assert np.allclose(sozinha, em_lote, atol=1e-4)


def test_vetorizador_semantico_serializa_sem_o_modelo_onnx():
    import joblib

    v = encoder.VetorizadorSemantico()
    buf = io.BytesIO()
    joblib.dump(v, buf)
    assert buf.tell() < 5_000                       # só a classe, não os 118 MB do modelo
    buf.seek(0)
    assert joblib.load(buf).transform(["teste"]).shape == (1, 384)


def test_votacao_sem_encoder_segue_com_os_ngramas(monkeypatch):
    """Encoder ausente em produção: o bot continua respondendo, só com menos contexto."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline

    from votacao import Votacao

    frases = ["quero artigos sobre cárie", "formata a referência abnt", "preciso de artigos sobre ansiedade", "monta a citação abnt"]
    rotulos = ["buscar", "formatar", "buscar", "formatar"]
    modelo = Votacao([
        ("ngramas", make_pipeline(TfidfVectorizer(), LogisticRegression()), 0.7),
        ("encoder", make_pipeline(encoder.VetorizadorSemantico(), LogisticRegression()), 0.3),
    ]).fit(frases, rotulos)

    def indisponivel(self, X):
        raise encoder.EncoderIndisponivel("simulado")

    monkeypatch.setattr(encoder.VetorizadorSemantico, "transform", indisponivel)
    prob = modelo.predict_proba(["artigos sobre cárie"])
    assert prob.shape == (1, 2) and np.isclose(prob.sum(), 1.0)
    assert modelo.ramos_ignorados_ == ["encoder"]

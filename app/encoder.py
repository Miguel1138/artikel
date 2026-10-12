"""Encoder de sentenças local (ONNX) para o classificador de intenções.

Transforma uma frase em um vetor de 384 números em que frases de SIGNIFICADO parecido ficam
perto ("relação entre pais e filhos" ~ "convivência de pais e filhos"), mesmo sem palavras em
comum. É isso que o TF-IDF não faz: ele só enxerga as palavras e os pares de palavras.

O modelo é o `paraphrase-multilingual-MiniLM-L12-v2` (Apache-2.0, 50+ idiomas, português
incluso), pré-treinado pela comunidade e rodando LOCAL em CPU, sem API, sem chave e sem rede
em tempo de uso. Ele só produz o vetor; quem decide a intenção é a regressão logística
treinada pela equipe sobre `data/intents.csv` (R3). Não gera texto e não é um LLM.

Os arquivos ficam em `models/encoder/` (fora do git): `python scripts/baixar_encoder.py`.
Se faltarem, o classificador segue só com os n-gramas e avisa (ver `votacao.py`).
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Sequence

import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin

from config import ARQ_ENCODER

MAX_TOKENS = 128          # perguntas de chat são curtas; truncar protege o tempo de resposta
TAM_LOTE = 32


class EncoderIndisponivel(RuntimeError):
    """Arquivos do modelo ou bibliotecas ausentes."""


def _canonico(texto) -> str:
    """Minúsculas e espaços únicos. Mantém acentos e pontuação: o modelo multilíngue os usa
    (ao contrário do TF-IDF, que os remove), mas "PROCURO" e "procuro" tokenizam diferente."""
    return " ".join(str(texto).lower().split())


class Encoder:
    def __init__(self, pasta: Path = ARQ_ENCODER):
        modelo, tokenizador = pasta / "model.onnx", pasta / "tokenizer.json"
        faltando = [p.name for p in (modelo, tokenizador) if not p.exists()]
        if faltando:
            raise EncoderIndisponivel(
                f"encoder ausente em {pasta.name}/ ({', '.join(faltando)}); "
                "rode: python scripts/baixar_encoder.py"
            )
        try:
            import onnxruntime as ort
            from tokenizers import Tokenizer
        except ImportError as exc:
            raise EncoderIndisponivel(f"falta instalar {exc.name}: pip install onnxruntime tokenizers") from exc

        opcoes = ort.SessionOptions()
        opcoes.intra_op_num_threads = max(1, min(4, os.cpu_count() or 1))
        self._sessao = ort.InferenceSession(str(modelo), opcoes, providers=["CPUExecutionProvider"])
        self._entradas = {i.name for i in self._sessao.get_inputs()}
        self._tokenizador = Tokenizer.from_file(str(tokenizador))
        self._tokenizador.enable_padding()
        self._tokenizador.enable_truncation(MAX_TOKENS)
        self._cache: dict[str, np.ndarray] = {}

    def codificar(self, textos: Sequence[str]) -> np.ndarray:
        """Matriz (n, 384) com vetores de norma 1; frases repetidas vêm do cache."""
        textos = [_canonico(t) for t in textos]
        novos = list(dict.fromkeys(t for t in textos if t not in self._cache))
        for i in range(0, len(novos), TAM_LOTE):
            lote = novos[i:i + TAM_LOTE]
            for texto, vetor in zip(lote, self._vetores(lote)):
                self._cache[texto] = vetor
        return np.vstack([self._cache[t] for t in textos]) if textos else np.zeros((0, 384))

    def _vetores(self, lote: list[str]) -> np.ndarray:
        enc = self._tokenizador.encode_batch(lote)
        ids = np.array([e.ids for e in enc], dtype=np.int64)
        mascara = np.array([e.attention_mask for e in enc], dtype=np.int64)
        entradas = {"input_ids": ids, "attention_mask": mascara}
        if "token_type_ids" in self._entradas:
            entradas["token_type_ids"] = np.zeros_like(ids)
        estados = self._sessao.run(None, entradas)[0]
        # pooling por média sobre os tokens reais (config do modelo), depois norma 1
        m = mascara[..., None]
        media = (estados * m).sum(axis=1) / m.sum(axis=1)
        return media / np.linalg.norm(media, axis=1, keepdims=True)


@lru_cache(maxsize=1)
def obter_encoder() -> Encoder:
    """Uma instância por processo (carregar o modelo leva ~4 s)."""
    return Encoder()


def encoder_disponivel() -> bool:
    try:
        obter_encoder()
        return True
    except EncoderIndisponivel:
        return False


class VetorizadorSemantico(BaseEstimator, TransformerMixin):
    """Etapa de pipeline do scikit-learn: texto bruto -> vetor semântico.

    Não guarda o modelo ONNX (que não serializa): grava só a si mesmo no .joblib e busca o
    encoder do processo ao transformar. Sem estado a ajustar, `fit` é vazio.
    """

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        return obter_encoder().codificar(list(X))

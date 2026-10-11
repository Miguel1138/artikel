"""Classificador de intenções (R3) — carga do modelo e predição com confiança.

O modelo é treinado por `scripts/treinar_classificador.py`. Se o arquivo não existir, a
API avisa no `/saude` em vez de quebrar: o resto do sistema continua utilizável.
"""
from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np

from config import ARQ_MODELO, INTENCOES
from preprocessamento import normalizar


class Classificador:
    def __init__(self, caminho: Path = ARQ_MODELO):
        self.caminho = caminho
        self.pacote: dict | None = None
        self.erro: str | None = None
        self._carregar()

    def _carregar(self) -> None:
        if not self.caminho.exists():
            self.erro = (
                f"modelo ausente em {self.caminho.name}; "
                "rode: python scripts/treinar_classificador.py"
            )
            return
        try:
            self.pacote = joblib.load(self.caminho)
        except Exception as exc:  # arquivo corrompido ou versão incompatível do sklearn
            self.erro = f"falha ao carregar o modelo: {exc}"

    @property
    def carregado(self) -> bool:
        return self.pacote is not None

    def prever(self, texto: str) -> tuple[str, float]:
        """Devolve (intenção, confiança). Sem modelo, cai na classe de abstenção."""
        if not self.carregado:
            return "fora_de_escopo", 0.0
        vetor = self.pacote["vetorizador"].transform([normalizar(texto)])
        modelo = self.pacote["modelo"]
        prob = modelo.predict_proba(vetor)[0]
        classes = list(modelo.classes_)
        i = int(np.argmax(prob))
        return classes[i], float(prob[i])

    def probabilidades(self, texto: str) -> dict[str, float]:
        """Todas as probabilidades, na ordem de `config.INTENCOES` (usado na avaliação)."""
        if not self.carregado:
            return {i: 0.0 for i in INTENCOES}
        vetor = self.pacote["vetorizador"].transform([normalizar(texto)])
        modelo = self.pacote["modelo"]
        prob = modelo.predict_proba(vetor)[0]
        return {c: float(p) for c, p in zip(modelo.classes_, prob)}


_cache: Classificador | None = None


def obter() -> Classificador:
    """Instância única por processo (o joblib carrega rápido, mas não a cada requisição)."""
    global _cache
    if _cache is None:
        _cache = Classificador()
    return _cache

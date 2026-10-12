"""Classificador de intenções (R3) — carga do modelo e predição com confiança.

O modelo é treinado por `scripts/treinar_classificador.py`. Se o arquivo não existir, a
API avisa no `/saude` em vez de quebrar: o resto do sistema continua utilizável.
"""
from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np

from config import ARQ_MODELO, INTENCOES
from encoder import encoder_disponivel


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

    def _probabilidades(self, texto: str) -> tuple[list, np.ndarray]:
        """(classes, probabilidades) para o texto BRUTO.

        O pré-processamento mora dentro do modelo gravado (ver treinar_classificador.py), então
        treino e inferência não têm como divergir. Aceita o formato antigo do .joblib
        (vetorizador e modelo separados) para não quebrar quem ainda não retreinou.
        """
        modelo = self.pacote["modelo"]
        if "vetorizador" in self.pacote:
            prob = modelo.predict_proba(self.pacote["vetorizador"].transform([texto]))[0]
        else:
            prob = modelo.predict_proba([texto])[0]
        return list(modelo.classes_), prob

    @property
    def avisos(self) -> list[str]:
        """Degradações em vigor (aparecem em /saude): o bot funciona, mas com menos contexto."""
        if self.carregado and "encoder" in self.pacote.get("ramos", []) and not encoder_disponivel():
            return ["encoder ausente: o classificador usa só n-gramas (rode scripts/baixar_encoder.py)"]
        return []

    @property
    def ramos_ignorados(self) -> list[str]:
        """Ramos do modelo que não rodaram (ex.: encoder ausente): o bot segue com menos contexto."""
        return list(getattr(self.pacote["modelo"], "ramos_ignorados_", [])) if self.carregado else []

    def prever(self, texto: str) -> tuple[str, float]:
        """Devolve (intenção, confiança). Sem modelo, cai na classe de abstenção."""
        if not self.carregado:
            return "fora_de_escopo", 0.0
        classes, prob = self._probabilidades(texto)
        i = int(np.argmax(prob))
        return classes[i], float(prob[i])

    def probabilidades(self, texto: str) -> dict[str, float]:
        """Todas as probabilidades, na ordem de `config.INTENCOES` (usado na avaliação)."""
        if not self.carregado:
            return {i: 0.0 for i in INTENCOES}
        classes, prob = self._probabilidades(texto)
        return {c: float(p) for c, p in zip(classes, prob)}


_cache: Classificador | None = None


def obter() -> Classificador:
    """Instância única por processo (o joblib carrega rápido, mas não a cada requisição)."""
    global _cache
    if _cache is None:
        _cache = Classificador()
    return _cache

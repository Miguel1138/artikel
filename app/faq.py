"""FAQ de busca (intenção `orientar_busca`).

Sem LLM: o texto da resposta é o que está escrito em `data/faq_busca.json`, escolhido por
similaridade. Assim a orientação dada é sempre a mesma que a equipe revisou.
"""
from __future__ import annotations

import json
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from config import ARQ_FAQ
from preprocessamento import normalizar


class Faq:
    def __init__(self, caminho: Path = ARQ_FAQ):
        self.caminho = caminho
        self.entradas: list[dict] = []
        self.erro: str | None = None
        self._vetorizador: TfidfVectorizer | None = None
        self._matriz = None
        self._carregar()

    def _carregar(self) -> None:
        if not self.caminho.exists():
            self.erro = f"FAQ ausente em {self.caminho.name}"
            return
        dados = json.loads(self.caminho.read_text(encoding="utf-8"))
        self.entradas = dados.get("entradas", [])
        if not self.entradas:
            self.erro = "a FAQ está vazia"
            return
        textos = [" ".join([e["titulo"], *e.get("perguntas", []), " ".join(e.get("tags", []))])
                  for e in self.entradas]
        self._vetorizador = TfidfVectorizer(preprocessor=normalizar, ngram_range=(1, 2), sublinear_tf=True)
        self._matriz = self._vetorizador.fit_transform(textos)

    @property
    def pronto(self) -> bool:
        return self._vetorizador is not None and bool(self.entradas)

    def responder(self, pergunta: str, area: str | None = None) -> tuple[dict | None, float]:
        """Entrada mais próxima e o score. `area` só desempata, não filtra."""
        if not self.pronto:
            return None, 0.0
        vetor = self._vetorizador.transform([pergunta])
        scores = cosine_similarity(vetor, self._matriz)[0]
        melhor, melhor_score = None, 0.0
        for i, entrada in enumerate(self.entradas):
            score = float(scores[i])
            if area and area in (entrada.get("areas") or []):
                score += 0.02
            if score > melhor_score:
                melhor, melhor_score = entrada, score
        return melhor, melhor_score

    def titulos(self) -> list[str]:
        return [e["titulo"] for e in self.entradas]


_cache: Faq | None = None


def obter() -> Faq:
    global _cache
    if _cache is None:
        _cache = Faq()
    return _cache

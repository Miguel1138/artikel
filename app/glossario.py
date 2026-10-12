"""Ponte pt <-> en da recuperação (glossário gerado com o Open Multilingual WordNet).

A base é majoritariamente em inglês e as perguntas são em português. `data/glossario_pt_en.json`
é gerado por `scripts/gerar_glossario.py` (NLTK + aprovação manual) e lido aqui sem nenhuma
dependência de NLTK. Complementa o `ALIASES` escrito à mão em `recuperacao.py`.

As chaves são pt sem acento. O índice é simétrico: uma pergunta em inglês ("gingivitis")
também acha o equivalente em português, que é o que está nos 40 artigos em pt.
"""
from __future__ import annotations

import json
from collections import defaultdict
from functools import lru_cache
from typing import Iterator

from config import ARQ_GLOSSARIO


@lru_cache(maxsize=1)
def _indice() -> dict[str, frozenset[str]]:
    if not ARQ_GLOSSARIO.exists():
        return {}
    dados = json.loads(ARQ_GLOSSARIO.read_text(encoding="utf-8"))
    indice: dict[str, set[str]] = defaultdict(set)
    for pt, equivalentes in dados.items():
        for en in equivalentes:
            indice[pt].add(en)
            indice[en].add(pt)
    return {termo: frozenset(valores) for termo, valores in indice.items()}


def _formas(termo: str) -> Iterator[str]:
    """O termo e suas formas-base simples: plural e feminino ('testes' -> 'teste', 'depressiva' -> 'depressivo')."""
    yield termo
    if termo.endswith("oes"):
        yield termo[:-3] + "ao"
    if termo.endswith("ais"):
        yield termo[:-3] + "al"
    if termo.endswith("es"):
        yield termo[:-2]
    if termo.endswith("s"):
        yield termo[:-1]
    if termo.endswith("as"):
        yield termo[:-2] + "o"
    if termo.endswith("a"):
        yield termo[:-1] + "o"


def equivalentes(termo: str) -> frozenset[str]:
    """Equivalentes pt/en do termo (sem acento, minúsculo). Vazio se o glossário não o conhece."""
    indice = _indice()
    achados: set[str] = set()
    for forma in _formas(termo):
        achados |= indice.get(forma, frozenset())
    achados.discard(termo)
    return frozenset(achados)

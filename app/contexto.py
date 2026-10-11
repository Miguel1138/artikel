"""Contexto mínimo de conversa (R1).

Guarda a última lista de artigos exibida para resolver referências como "o segundo
artigo", "a última referência", "formata o terceiro". Em memória, por sessão, sem dado
pessoal — o documento proíbe histórico por usuário.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

# Quanto tempo o contexto continua válido (segundos). Depois disso o bot pede a busca de novo.
TTL = 30 * 60

ORDINAIS = {
    "primeiro": 1, "primeira": 1, "1": 1, "um": 1, "uma": 1,
    "segundo": 2, "segunda": 2, "2": 2, "dois": 2, "duas": 2,
    "terceiro": 3, "terceira": 3, "3": 3, "tres": 3,
    "quarto": 4, "quarta": 4, "4": 4, "quatro": 4,
    "quinto": 5, "quinta": 5, "5": 5, "cinco": 5,
}

_REFERENCIA = re.compile(
    r"\b(primeir[oa]|segund[oa]|terceir[oa]|quart[oa]|quint[oa]|"
    r"ultim[oa]|penultim[oa]|anterior|esse|esta|este|isso|"
    r"\d)\b",
    re.I,
)


@dataclass
class Contexto:
    artigos: list[dict] = field(default_factory=list)
    atualizado_em: float = 0.0
    ultima_busca: str | None = None
    ultima_intencao: str | None = None
    abstencao_aos_seguidos: int = 0

    # ------------------------------------------------------------ ciclo de vida
    def expirado(self, agora: float | None = None) -> bool:
        return (agora or time.time()) - self.atualizado_em > TTL

    def guardar_artigos(self, artigos: list[dict], busca: str | None = None) -> None:
        self.artigos = artigos
        self.ultima_busca = busca or self.ultima_busca
        self.atualizado_em = time.time()

    def limpar(self) -> None:
        self.artigos = []
        self.ultima_busca = None
        self.atualizado_em = 0.0

    @property
    def tem_artigos(self) -> bool:
        return bool(self.artigos) and not self.expirado()

    # ------------------------------------------------------------ resolução
    def cita_lista(self, texto: str) -> bool:
        """True quando a frase se refere à lista já exibida."""
        return bool(_REFERENCIA.search(texto))

    def posicao(self, texto: str) -> int | None:
        """Posição 1-based citada na frase ('o segundo artigo' -> 2).

        Ordinais são verificados antes dos algarismos: "os 2 artigos" tem o dígito 2, mas
        em "a referência do segundo" o dígito não existe. Quando os dois aparecem, o
        ordinal vem primeiro porque é ele que aponta para a lista exibida.
        """
        t = texto.lower()
        # `\búltim` casa "último" mas não "penúltimo" (que tem 'n' antes do 'ú').
        if re.search(r"\bultim|\búltim", t):
            return len(self.artigos) if self.artigos else None
        if "penultimo" in t or "penúltimo" in t:
            return max(len(self.artigos) - 1, 1) if self.artigos else None
        for palavra, n in ORDINAIS.items():
            if palavra.isdigit():
                continue
            if re.search(rf"\b{palavra}\b", t):
                return n
        m = re.search(r"\b(\d)\b", t)
        if m:
            return int(m.group(1))
        return None

    def artigo_citado(self, texto: str) -> dict | None:
        """Artigo ao qual a frase se refere, ou None."""
        if not self.tem_artigos or not self.cita_lista(texto):
            return None
        pos = self.posicao(texto)
        if pos is None:
            return None
        if 1 <= pos <= len(self.artigos):
            return self.artigos[pos - 1]
        return None


class Sessoes:
    """Contexto por sessão. `sessao` vem do cliente; nada é persistido em disco."""

    def __init__(self, maximo: int = 200):
        self._dados: dict[str, Contexto] = {}
        self.maximo = maximo

    def obter(self, sessao: str) -> Contexto:
        ctx = self._dados.get(sessao)
        if ctx is None:
            if len(self._dados) >= self.maximo:      # descarta a sessão mais antiga
                mais_antiga = min(self._dados, key=lambda k: self._dados[k].atualizado_em)
                self._dados.pop(mais_antiga, None)
            ctx = Contexto()
            self._dados[sessao] = ctx
        return ctx

    def limpar(self, sessao: str) -> None:
        self._dados.pop(sessao, None)


sessoes = Sessoes()

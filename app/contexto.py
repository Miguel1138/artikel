"""Contexto mínimo de conversa (R1).

Guarda a última lista de artigos exibida para resolver referências como "o segundo
artigo", "a última referência", "formata o terceiro", e a pergunta de esclarecimento
pendente ("você quer artigos sobre X?") até a próxima mensagem. Em memória, por sessão,
sem dado pessoal — o documento proíbe histórico por usuário.
"""
from __future__ import annotations

import re
import time
import unicodedata
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

# Respostas curtas a uma pergunta de esclarecimento. Casam a mensagem INTEIRA: "quero artigos
# sobre cárie" e "sim, mas sobre crianças" são perguntas novas, não confirmações.
_SIM = re.compile(r"(sim|s|isso|isso mesmo|exato|exatamente|pode|pode ser|quero|claro|ok|certo|"
                  r"correto|beleza|isso ai|com certeza)( (sim|pode|quero|isso|por favor|obrigad[oa]))*")
_NAO = re.compile(r"(nao|n|nenhum|nenhuma|errado|negativo|outra coisa|nao obrigad[oa]|"
                  r"nao (e|era) (isso|outra coisa|nada disso))")


def _normalizar_resposta(texto: str) -> str:
    sem = "".join(c for c in unicodedata.normalize("NFKD", texto.lower()) if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9\s]", " ", sem).split())


def resposta_curta(texto: str) -> bool:
    """True para "sim", "não", "ok"... sozinhos: só fazem sentido com uma pergunta em aberto."""
    t = _normalizar_resposta(texto)
    return bool(_SIM.fullmatch(t) or _NAO.fullmatch(t))


@dataclass
class Esclarecimento:
    """Pergunta feita ao usuário: a mensagem original e as ações oferecidas, em ordem."""

    pergunta: str
    opcoes: list[tuple[str, str]]          # (intenção, rótulo do botão)
    confianca: float
    criado_em: float = field(default_factory=time.time)

    def resolver(self, texto: str) -> str | None:
        """Intenção escolhida, "" para recusa ou None quando a mensagem é outra pergunta."""
        t = _normalizar_resposta(texto)
        for intencao, rotulo in self.opcoes:
            if t == _normalizar_resposta(rotulo):
                return intencao
        if t.isdigit() and 1 <= int(t) <= len(self.opcoes):
            return self.opcoes[int(t) - 1][0]
        if _NAO.fullmatch(t):
            return ""
        if _SIM.fullmatch(t):
            return self.opcoes[0][0]
        return None


@dataclass
class Contexto:
    artigos: list[dict] = field(default_factory=list)
    atualizado_em: float = 0.0
    ultima_busca: str | None = None
    ultima_intencao: str | None = None
    abstencao_aos_seguidos: int = 0
    esclarecimento: Esclarecimento | None = None

    def tomar_esclarecimento(self) -> Esclarecimento | None:
        """Devolve e apaga a pergunta pendente: ela vale só para a mensagem seguinte."""
        pendente, self.esclarecimento = self.esclarecimento, None
        if pendente is None or time.time() - pendente.criado_em > TTL:
            return None
        return pendente

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
        self.esclarecimento = None
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

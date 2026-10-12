"""Pré-processamento compartilhado pelo treino e pela inferência.

O documento exige que o texto seja tratado **do mesmo jeito** nos dois lados (seção 7,
módulo "Pré-processamento"): minúsculas, acentos e stopwords. Por isso este módulo não
importa nada de `intencoes.py` nem de `recuperacao.py` — ele é a única implementação.
"""
from __future__ import annotations

import re
import unicodedata

# Stopwords do domínio: português + inglês (as perguntas misturam os dois idiomas).
STOPWORDS = {
    # português
    "a", "ao", "aos", "aquela", "aquele", "aquilo", "as", "até", "com", "como", "da",
    "das", "de", "dela", "dele", "depois", "do", "dos", "e", "ela", "ele", "em", "entre",
    "era", "essa", "esse", "esta", "este", "eu", "foi", "há", "isso", "isto", "já", "lhe",
    "mais", "mas", "me", "mesmo", "meu", "minha", "muito", "na", "nas", "não", "no", "nos",
    "nós", "o", "os", "ou", "para", "pela", "pelo", "por", "que", "quem", "se", "sem",
    "ser", "seu", "só", "sobre", "sua", "também", "tem", "tenho", "ter", "um", "uma",
    "você",
    # inglês
    "about", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does", "for",
    "from", "how", "i", "in", "is", "it", "me", "my", "of", "on", "or", "the", "to",
    "what", "where", "which", "with", "you",
}

# Palavras que carregam a intenção e nunca devem ser removidas, mesmo curtas.
NUCLEARES = {
    "abnt", "artigo", "artigos", "busca", "citar", "confiavel", "doi", "fonte",
    "palavra", "palavras", "periodico", "referencia", "revista", "scielo", "tcc",
    "wikipedia", "nbr", "6023",
}

_NAO_ALFANUM = re.compile(r"[^a-z0-9\s]+")
_ESPACOS = re.compile(r"\s+")

# Radicais para casar plurais e flexões simples do português sem stemmer externo.
SUFIXOS = ("mente", "coes", "cao", "oes", "ais", "eis", "ns", "s", "es")


def sem_acento(texto: str) -> str:
    """Remove diacríticos: 'referência' -> 'referencia'."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )


def tokenizar(texto: str) -> list[str]:
    """Texto -> tokens normalizados (sem acento, sem pontuação)."""
    if not texto:
        return []
    limpo = _NAO_ALFANUM.sub(" ", sem_acento(texto).lower())
    return _ESPACOS.sub(" ", limpo).strip().split()


def radical(token: str) -> str:
    """Radical simples: corta o sufixo mais longo que ainda deixe 4 caracteres."""
    if token in NUCLEARES or len(token) <= 4:
        return token
    for sufixo in SUFIXOS:
        if token.endswith(sufixo) and len(token) - len(sufixo) >= 4:
            return token[: -len(sufixo)]
    return token


def normalizar(texto: str, remover_stopwords: bool = True, usar_radical: bool = False) -> str:
    """Versão normalizada do texto, pronta para o vetorizador.

    `usar_radical` fica desligado por padrão: o TF-IDF já lida bem com flexões e o
    radical agressivo aumenta os falsos positivos entre intenções.
    """
    tokens = tokenizar(texto)
    if remover_stopwords:
        tokens = [t for t in tokens if t not in STOPWORDS]
    if usar_radical:
        tokens = [radical(t) for t in tokens]
    return " ".join(tokens)


def normalizar_intencao(texto: str) -> str:
    """Normalização do classificador de intenções: mantém as palavras funcionais.

    "como", "que", "onde", "para" e "não" são justamente o que separa "como busco um
    artigo?" (orientar) de "busco um artigo" (buscar). Remover stopwords tirava esse sinal:
    a validação cruzada foi de 0,849 para 0,891 só por mantê-las. Função de módulo (e não
    lambda) para o joblib conseguir gravá-la junto com o vetorizador.
    """
    return normalizar(texto, remover_stopwords=False)


def termos_relevantes(texto: str) -> list[str]:
    """Termos usados para medir sobreposição entre a pergunta e a base.

    A pergunta "artigos sobre cárie infantil" precisa casar com o resumo do artigo; por
    isso aqui os radicais entram (é uma comparação de conteúdo, não de intenção).
    """
    return [radical(t) for t in tokenizar(texto) if t not in STOPWORDS]

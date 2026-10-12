"""Pré-processamento de texto + Bag of Words, em um único arquivo reutilizável.

Não importa nada do Artikel: para usar em outro projeto, copie só este arquivo. Depende
apenas da biblioteca padrão; o scikit-learn só é importado em `criar_vetorizador`, e o
NLTK é opcional (`obter_stopwords(usar_nltk=True)` e `lematizador_wordnet`).

Origem: as etapas do notebook `bert-for-articles` (minúsculas, remoção de URL/HTML/
pontuação/dígitos, stopwords, lematização, junção de título e texto, descarte de textos
curtos), sem depender de `nltk.download` em tempo de execução.

Uso mínimo:

    from preprocessador_generico import Preprocessador, criar_vetorizador, obter_stopwords

    pre = Preprocessador(stopwords=obter_stopwords("pt", "en"))
    vetor = criar_vetorizador("bow", pre, ngramas=(1, 2))
    X = vetor.fit_transform(frases)            # contagem de palavras (Bag of Words)

A mesma instância `pre` deve ser usada no treino e na inferência: ao ir dentro do
vetorizador (`preprocessor=pre`), ela é gravada junto com o modelo.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, Iterable, Sequence

# --- Stopwords embutidas -------------------------------------------------------------
# Listas curtas de propósito: palavras interrogativas e de negação ("como", "onde",
# "não") ficam FORA, porque em classificação de intenção elas costumam ser o sinal.
# Passe sua própria lista ao `Preprocessador` quando o domínio pedir outra.
STOPWORDS_PT = frozenset({
    "a", "ao", "aos", "as", "com", "da", "das", "de", "do", "dos", "e", "em", "na", "nas",
    "no", "nos", "o", "os", "ou", "para", "pela", "pelo", "por", "um", "uma", "uns", "umas",
    "se", "seu", "sua", "meu", "minha", "me", "te", "lhe",
})
STOPWORDS_EN = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "is", "it", "of",
    "on", "or", "the", "to", "with",
})
_STOPWORDS_EMBUTIDAS = {"pt": STOPWORDS_PT, "en": STOPWORDS_EN}
_NOME_NLTK = {"pt": "portuguese", "en": "english", "es": "spanish", "fr": "french"}

_URL = re.compile(r"https?://\S+|www\.\S+")
_HTML = re.compile(r"<[^>]+>")
_ESPACOS = re.compile(r"\s+")


def sem_acento(texto: str) -> str:
    """Remove diacríticos: 'referência' -> 'referencia'."""
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


@lru_cache(maxsize=None)
def _nao_alfanumerico(minusculas: bool, acentos_removidos: bool, numeros: bool) -> re.Pattern:
    """O que sobra de um texto limpo: letras e (opcionalmente) dígitos."""
    if acentos_removidos:
        letras = "a-z" if minusculas else "a-zA-Z"
        return re.compile(rf"[^{letras}{'' if numeros else '0-9'}\s]+")
    # Com acento preservado, vale qualquer letra Unicode; "_" não é separador de palavra.
    return re.compile(r"[^\w\s]+|_+" if not numeros else r"[^\w\s]+|_+|\d+")


def _vazio(texto) -> bool:
    return texto is None or (isinstance(texto, float) and texto != texto)  # None ou NaN


@dataclass(frozen=True)
class Preprocessador:
    """Limpeza de texto configurável. Instância imutável, chamável e serializável (joblib).

    `stopwords` e `preservar` são normalizadas pelo próprio pré-processador na criação,
    então "não" ou "Você" casam mesmo com `remover_acentos=True`. `preservar` vence
    `stopwords`, o tamanho mínimo e a redução: use para as palavras que carregam sentido.
    `reducao` é qualquer `str -> str` (stemmer ou lematizador), aplicada depois das
    stopwords.
    """

    minusculas: bool = True
    remover_acentos: bool = True
    remover_urls: bool = True
    remover_html: bool = True
    remover_numeros: bool = False
    stopwords: Iterable[str] = frozenset()
    preservar: Iterable[str] = frozenset()
    tamanho_minimo: int = 1
    reducao: Callable[[str], str] | None = None

    def __post_init__(self) -> None:
        for campo in ("stopwords", "preservar"):
            normalizadas = {t for palavra in getattr(self, campo) for t in self._tokens_brutos(palavra)}
            object.__setattr__(self, campo, frozenset(normalizadas))

    # -- etapas ----------------------------------------------------------------------
    def limpar(self, texto) -> str:
        """Texto -> texto limpo (sem stopwords): URLs, HTML, acentos, pontuação, dígitos."""
        return " ".join(self._tokens_brutos(texto))

    def tokenizar(self, texto, remover_stopwords: bool = True) -> list[str]:
        """Texto -> tokens. `remover_stopwords=False` mantém tudo, para comparar efeitos."""
        tokens = [t for t in self._tokens_brutos(texto) if self._comprimento_ok(t)]
        if remover_stopwords:
            tokens = [t for t in tokens if t in self.preservar or t not in self.stopwords]
        if self.reducao is not None:
            tokens = [t if t in self.preservar else self.reducao(t) for t in tokens]
        return tokens

    def __call__(self, texto) -> str:
        """Forma de uso como `preprocessor=` do vetorizador do scikit-learn."""
        return " ".join(self.tokenizar(texto))

    def transformar(self, textos: Iterable) -> list[str]:
        return [self(t) for t in textos]

    # -- internos --------------------------------------------------------------------
    def _comprimento_ok(self, token: str) -> bool:
        return len(token) >= self.tamanho_minimo or token in self.preservar

    def _tokens_brutos(self, texto) -> list[str]:
        if _vazio(texto):
            return []
        texto = str(texto)
        if self.remover_urls:
            texto = _URL.sub(" ", texto)
        if self.remover_html:
            texto = _HTML.sub(" ", texto)
        if self.minusculas:
            texto = texto.lower()
        if self.remover_acentos:
            texto = sem_acento(texto)
        texto = _nao_alfanumerico(self.minusculas, self.remover_acentos, self.remover_numeros).sub(" ", texto)
        return _ESPACOS.sub(" ", texto).strip().split()


# --- Bag of Words --------------------------------------------------------------------
TIPOS_VETORIZADOR = ("bow", "bow_binario", "tfidf")


def criar_vetorizador(
    tipo: str = "bow",
    preprocessador: Callable[[str], str] | None = None,
    *,
    ngramas: tuple[int, int] = (1, 1),
    min_df: int | float = 1,
    max_df: int | float = 1.0,
    max_features: int | None = None,
    caracteres: tuple[int, int] | None = None,
):
    """Vetorizador do scikit-learn já ligado ao pré-processador.

    `tipo`:
      "bow"         contagem de palavras (Bag of Words clássico)
      "bow_binario" presença/ausência da palavra (1 ou 0), ignora repetição
      "tfidf"       contagem ponderada pela raridade da palavra no corpus

    Bag of Words ignora a ordem das palavras. O único "contexto" que ele captura vem de
    `ngramas`: (1, 2) conta também pares vizinhos ("busca booleana"), (1, 3) trios.
    `preprocessador` é qualquer `str -> str` (uma instância de `Preprocessador`, por
    exemplo); sem ele, usa um `Preprocessador()` sem stopwords.

    `caracteres=(2, 5)` soma n-gramas de LETRAS dentro de cada palavra ("referenciar" e
    "referência" passam a compartilhar "refer", "feren"...). Não depende de lista de
    palavras nem de stemmer, então cobre plural, flexão verbal e erro de digitação; o
    resultado é um `FeatureUnion` (palavras + caracteres), sem `vocabulary_` próprio.
    """
    from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer

    if tipo not in TIPOS_VETORIZADOR:
        raise ValueError(f"tipo inválido: {tipo!r}; use um de {TIPOS_VETORIZADOR}")
    comum = dict(
        preprocessor=preprocessador or Preprocessador(),
        ngram_range=tuple(ngramas),
        min_df=min_df,
        max_df=max_df,
        max_features=max_features,
    )

    def montar(**extra):
        if tipo == "tfidf":
            return TfidfVectorizer(sublinear_tf=True, **{**comum, **extra})
        return CountVectorizer(binary=(tipo == "bow_binario"), **{**comum, **extra})

    palavras = montar()
    if caracteres is None:
        return palavras

    from sklearn.pipeline import FeatureUnion

    return FeatureUnion([
        ("palavras", palavras),
        ("caracteres", montar(analyzer="char_wb", ngram_range=tuple(caracteres))),
    ])


# --- Stopwords e lematização opcionais (NLTK) ---------------------------------------
def obter_stopwords(*idiomas: str, usar_nltk: bool = False, extras: Iterable[str] = ()) -> frozenset:
    """União das stopwords embutidas dos idiomas ("pt", "en") com `extras`.

    Com `usar_nltk=True` soma as listas do NLTK **se estiverem instaladas**; sem rede ou
    sem o corpus, cai nas embutidas em silêncio (o `nltk.download` do notebook falhava
    assim). Atenção: as listas do NLTK incluem "não", "como", "que" — palavras que, em
    intenção de chatbot, quase sempre devem ser preservadas.
    """
    desconhecidos = [i for i in idiomas if i not in _STOPWORDS_EMBUTIDAS]
    if desconhecidos:
        raise ValueError(f"idioma sem lista embutida: {desconhecidos}; use `extras=`")
    palavras = set(extras)
    for idioma in idiomas:
        palavras |= _STOPWORDS_EMBUTIDAS[idioma]
        if usar_nltk:
            try:
                from nltk.corpus import stopwords

                palavras |= set(stopwords.words(_NOME_NLTK[idioma]))
            except Exception:  # sem nltk, sem corpus ou idioma não mapeado
                pass
    return frozenset(palavras)


def lematizador_wordnet() -> Callable[[str], str] | None:
    """`WordNetLemmatizer.lemmatize` (inglês) ou None se NLTK/WordNet não estiver disponível."""
    try:
        from nltk.stem import WordNetLemmatizer

        lematizador = WordNetLemmatizer()
        lematizador.lemmatize("tests")  # falha aqui, e não no meio do treino, se faltar o corpus
        return lematizador.lemmatize
    except Exception:
        return None


# --- Utilidades de dataset (as etapas "de tabela" do notebook) ------------------------
def juntar_campos(*partes, separador: str = " ") -> str:
    """Junta título + texto etc., ignorando None/NaN: `juntar_campos(titulo, resumo)`."""
    return separador.join(str(p) for p in partes if not _vazio(p) and str(p).strip())


def descartar_curtos(textos: Sequence[str], *paralelas: Sequence, minimo: int = 20) -> tuple[list, ...]:
    """Remove textos com menos de `minimo` caracteres, mantendo `paralelas` (rótulos...) alinhadas.

    Devolve `(textos, *paralelas)` filtrados.
    """
    manter = [i for i, t in enumerate(textos) if len(t) >= minimo]
    return tuple([seq[i] for i in manter] for seq in (textos, *paralelas))


def estatisticas_tamanho(textos: Iterable[str]) -> dict[str, float]:
    """Mínimo, máximo, média, mediana e percentil 95 do tamanho em palavras."""
    tamanhos = sorted(len(t.split()) for t in textos)
    if not tamanhos:
        return {}
    n = len(tamanhos)
    meio = n // 2
    return {
        "minimo": tamanhos[0],
        "maximo": tamanhos[-1],
        "media": sum(tamanhos) / n,
        "mediana": tamanhos[meio] if n % 2 else (tamanhos[meio - 1] + tamanhos[meio]) / 2,
        "p95": tamanhos[min(n - 1, int(0.95 * n))],
    }

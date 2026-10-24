"""Recuperação por similaridade com reordenação por curadoria (R3, objetivo 3).

- Índice TF-IDF sobre título + resumo + palavras-chave (BM25 é alternativa: ver README).
- Similaridade de cosseno como score base.
- Reordenação: bônus pequenos por revisão por pares, indexação, ano e área.
- O índice é construído sobre a base; o modelo de intenções nunca treina nela.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

import glossario
from preprocessamento import STOPWORDS as STOPWORDS_PP, sem_acento as sem_acento_pp
from config import (
    ARQ_BASE,
    ARQ_PERIODICOS,
    BONUS_ANO_RECENTE,
    BONUS_INDEXACAO,
    BONUS_INDEXACAO_MAX,
    BONUS_MESMA_AREA,
    BONUS_REVISAO,
    COBERTURA_MINIMA,
    MAX_TERMOS_TEMA,
    MIN_ARTIGOS_TEMA,
    MIN_COBERTURA_COMPLETA,
    TERMOS_DO_SISTEMA,
    TOP_K,
)


@dataclass
class Candidato:
    artigo: dict
    score: float
    similaridade: float
    motivos: list[str] = field(default_factory=list)
    cobertura: float = 1.0


# Palavras que aparecem em quase toda pergunta e não distinguem tema. Entram na
# similaridade, mas são ignoradas na hora de medir cobertura temática.
# "saude", "clinica" e afins entram porque no projeto elas qualificam o contexto (saúde é
# área de aplicação em Computação, Odontologia e Psicologia), não o tema buscado: sem isso,
# "aprendizado de máquina na saúde" exigiria a palavra "saúde" em todo artigo de Computação.
GENERICAS = {
    "artigo", "artigos", "estudo", "estudos", "pesquisa", "pesquisas", "preciso",
    "quero", "queria", "gostaria", "tenho", "tem", "temos", "fonte", "fontes",
    "referencia", "referencias", "trabalho", "trabalhos", "tema", "temas", "sobre",
    "recente", "recentes", "atual", "atuais", "coisa", "coisas", "material",
    "paper", "papers", "study", "studies", "research", "article", "articles",
    "need", "want", "about", "recent", "source", "sources", "reference", "references",
    "saude", "health", "healthcare", "clinica", "clinical", "paciente", "pacientes",
    "patient", "patients",
    # Verbos e moldes de pergunta: aparecem em quase toda frase e não dizem o tema.
    # Sem eles, "cadê artigos sobre periodontia" virava dois termos temáticos ("cade" e
    # "periodontia") e a cobertura ficava abaixo do limiar mesmo achando o artigo certo.
    "cade", "acha", "achar", "acho", "encontro", "encontrar", "busca", "buscar", "busco",
    "procuro", "procurar", "manda", "mandar", "mostra", "mostrar", "lista", "listar",
    "indica", "indicar", "sugere", "sugerir", "da", "dar", "ver", "quais", "qual",
    "onde", "como", "tem", "existe", "existem", "ha", "find", "show", "list", "give",
    "suggest", "looking", "search",
    # Moldes de pedido que o dicionário acima ainda não cobria: sem eles viravam termo
    # temático sem equivalente na base e derrubavam a cobertura de um artigo certo
    # ("quais pesquisas tratam de gengivite" exigia "tratam").
    "bibliografia", "bibliografias", "literatura", "algo", "alguma", "algum", "alguns",
    "algumas", "tratam", "trata", "tratar", "dizem", "fala", "falam", "ler", "leitura",
    "leituras", "literature", "bibliography", "something", "anything",
    "primeira", "primeiras", "primeiro", "primeiros",
    # Adjetivos de tamanho/ligação e conectivos que não dizem o tema ("crianças pequenas",
    # "IA aplicada à saúde", "durante a pandemia"): sem correspondência, pesavam como o termo
    # mais raro da pergunta e derrubavam a cobertura.
    "pequena", "pequenas", "pequeno", "pequenos", "grande", "grandes",
    "aplicada", "aplicadas", "aplicado", "aplicados", "aplicacao", "aplicacoes",
    "durante", "quando", "atraves", "acerca", "relacionado", "relacionada",
    "relacionados", "relacionadas", "referente", "referentes",
}

# Palavras funcionais (o mesmo conjunto que o pré-processamento usa para as intenções):
# "relação ENTRE pais e filhos" não pode exigir a palavra "entre" no artigo.
_FUNCIONAIS = {sem_acento_pp(p) for p in STOPWORDS_PP}

# Equivalências pt <-> en usadas na conferência de cobertura. São **sinônimos**, não
# termos "relacionados": colocar "dental" como equivalente de "clareamento" fazia qualquer
# artigo de Odontologia cobrir a pergunta sobre clareamento. Cada termo só entra aqui
# quando pode substituir o outro em uma busca de verdade.
ALIASES = {
    "clareamento": {"whitening", "bleaching"},
    "whitening": {"clareamento", "bleaching"},
    "bleaching": {"clareamento", "whitening"},
    "carie": {"caries", "carious", "decay"},
    "caries": {"carie", "carious", "decay"},
    "dental": {"tooth", "teeth", "dentistry", "dentaria", "dentario"},
    "dentario": {"dental", "tooth", "teeth"},
    "dentarios": {"dental", "tooth", "teeth"},
    "dentaria": {"dental", "tooth", "teeth"},
    "odontologia": {"dentistry"}, "dentistry": {"odontologia"},
    "periodontal": {"periodontitis", "periodontology", "periodontia", "gum"},
    "periodontia": {"periodontology", "periodontitis", "periodontal"},
    "periodontitis": {"periodontal", "periodontia", "periodontology"},
    "periodontology": {"periodontia", "periodontal", "periodontitis"},
    "implante": {"implant"}, "implantes": {"implants"}, "implant": {"implante"},
    "implants": {"implantes"},
    "ansiedade": {"anxiety"}, "anxiety": {"ansiedade"},
    "depressao": {"depression"}, "depression": {"depressao"},
    "universitarios": {"university students", "undergraduate", "college students"},
    "estudantes": {"students"}, "students": {"estudantes"},
    "aprendizado": {"learning"}, "aprendizagem": {"learning"}, "learning": {"aprendizado"},
    "maquina": {"machine"}, "machine": {"maquina"},
    "linguagem": {"language"}, "language": {"linguagem"},
    "seguranca": {"security"}, "security": {"seguranca"},
    "informacao": {"information"}, "information": {"informacao"},
    "engenharia": {"engineering"}, "engineering": {"engenharia"},
    "saude": {"health", "healthcare"}, "health": {"saude"},
    "infantil": {"child", "childhood", "pediatric", "children"},
    "criancas": {"children", "child", "pediatric"},
    "children": {"criancas", "infantil"},
    "idosos": {"elderly", "aging"}, "trabalho": {"work", "workplace", "occupational"},
    "workplace": {"trabalho"},
    "desenvolvimento": {"development"}, "development": {"desenvolvimento"},
    "privacidade": {"privacy"}, "privacy": {"privacidade"},
}

def equivalentes(termo: str) -> set[str]:
    """Equivalentes pt/en do termo: o `ALIASES` à mão mais o glossário do OMW (ver glossario.py)."""
    return set(ALIASES.get(termo, ())) | set(glossario.equivalentes(termo))


_MARCA_PALAVRA = re.compile(r"[^a-z0-9\s]")

# Casas decimais da cobertura temática. O valor é o que decide se o artigo passa do
# limiar, então ele é arredondado antes da comparação: sem isso, ruído de ponto
# flutuante na soma muda a decisão entre duas execuções iguais.
_PRECISAO_COBERTURA = 9

# Conceitos que só valem juntos. Cada tupla é um conceito; se todos os termos dela
# aparecem na pergunta, ela deixa de ser avaliada termo a termo e passa a exigir que o
# artigo tenha o conceito inteiro. Sem isso, um artigo sobre "processos de aprendizagem"
# cobria a busca por "aprendizado de máquina".
CONCEITOS: tuple[tuple[str, ...], ...] = (
    ("aprendizado", "maquina"),
    ("machine", "learning"),
    ("aprendizagem", "maquina"),
    ("processamento", "linguagem", "natural"),
    ("natural", "language", "processing"),
    ("seguranca", "informacao"),
    ("information", "security"),
    ("engenharia", "software"),
    ("software", "engineering"),
    ("inteligencia", "artificial"),
    ("artificial", "intelligence"),
    ("saude", "mental"),
    ("mental", "health"),
    ("transtorno", "ansiedade"),
    ("transtornos", "ansiedade"),
    ("anxiety", "disorder"),
    ("anxiety", "disorders"),
    ("clareamento", "dental"),
    ("doenca", "periodontal"),
    ("periodontal", "disease"),
    ("carie", "infantil"),
    ("early", "childhood", "caries"),
    ("implante", "dentario"),
    ("dental", "implant"),
    ("desenvolvimento", "infantil"),
    ("child", "development"),
)


# Palavras que revelam a área da pergunta (sem acento, minúsculas).
PISTAS_AREA = {
    "computacao": ("computacao", "software", "algoritmo", "machine learning",
                   "aprendizado de maquina", "inteligencia artificial", "dados",
                   "programacao", "rede neural", "seguranca da informacao"),
    "odontologia": ("odontologia", "dental", "dente", "carie", "periodontal",
                    "clareamento", "implante", "bucal", "flúor", "fluor"),
    "psicologia": ("psicologia", "ansiedade", "depressao", "mental", "burnout",
                   "universitarios", "terapia", "comportamento"),
}


def sem_acento(texto: str) -> str:
    """Minúsculas e sem diacríticos (o `sem_acento` do pré-processamento, que não baixa a caixa)."""
    return sem_acento_pp(texto or "").lower()


class Motor:
    """Índice da base curada. Carregado uma vez por processo."""

    def __init__(self, arq_base: Path = ARQ_BASE, arq_periodicos: Path = ARQ_PERIODICOS):
        self.artigos: list[dict] = []
        self.periodicos_por_issn: dict[str, dict] = {}
        self.erro: str | None = None
        self._vetorizador: TfidfVectorizer | None = None
        self._matriz = None
        self._idf: dict[str, float] = {}
        self._faixa_idf: tuple[float, float] = (0.0, 0.0)
        self._textos_norm: list[str] = []
        self._palavras_doc: list[set[str]] = []
        self._cache_peso: dict[str, float] = {}
        self._cache_df: dict[str, int] = {}
        self._carregar(arq_base, arq_periodicos)

    # ------------------------------------------------------------ carga
    def _carregar(self, arq_base: Path, arq_periodicos: Path) -> None:
        if not arq_base.exists():
            self.erro = (
                f"base ausente em {arq_base.name}; "
                "rode: python scripts/coleta/pipeline.py"
            )
            return
        self.artigos = json.loads(arq_base.read_text(encoding="utf-8"))
        if arq_periodicos.exists():
            for p in json.loads(arq_periodicos.read_text(encoding="utf-8")):
                for issn in p.get("issn", []):
                    self.periodicos_por_issn.setdefault(issn, p)
        if not self.artigos:
            self.erro = "a base está vazia"
            return
        documentos = [self._documento(a) for a in self.artigos]
        # `max_df=0.6` melhora o índice em bases grandes, mas com poucos documentos o
        # scikit-learn recusa (max_df < min_df). Em base pequena o limite não é aplicado.
        max_df = 0.6 if len(documentos) > 3 else 1.0
        self._vetorizador = TfidfVectorizer(
            lowercase=True, sublinear_tf=True, ngram_range=(1, 2), min_df=1, max_df=max_df
        )
        self._matriz = self._vetorizador.fit_transform(documentos)
        self._idf = self._calcular_idf(documentos)
        self._faixa_idf = (min(self._idf.values(), default=0.0), max(self._idf.values(), default=0.0))
        # Texto normalizado de cada artigo, para contar em quantos aparece um conceito (_peso).
        self._textos_norm = [_MARCA_PALAVRA.sub(" ", sem_acento(d)) for d in documentos]
        self._palavras_doc = [set(t.split()) for t in self._textos_norm]
        self._cache_peso = {}
        self._cache_df = {}

    @staticmethod
    def _documento(artigo: dict) -> str:
        """Título pesa mais que o resto: aparece duas vezes no documento indexado."""
        titulo = artigo.get("titulo") or ""
        resumo = artigo.get("resumo") or ""
        chaves = " ".join(artigo.get("palavras_chave") or [])
        return f"{titulo} {titulo} {chaves} {resumo}"

    @staticmethod
    def _termos_consulta(consulta: str) -> set[str]:
        """Termos que identificam o tema da pergunta (sem genéricos, sem acento)."""
        limpo = _MARCA_PALAVRA.sub(" ", sem_acento(consulta))
        return {t for t in limpo.split()
                if len(t) >= 4 and t not in GENERICAS and t not in _FUNCIONAIS}

    @staticmethod
    def _calcular_idf(documentos: list[str]) -> dict[str, float]:
        """Raridade de cada palavra no vocabulário da base (idf suavizado).

        Serve para pesar a cobertura temática: casar uma palavra rara ("clareamento")
        vale muito mais que casar uma palavra comum ("dental", "informação").
        """
        n = len(documentos) or 1
        contagem = Counter(
            palavra for doc in documentos
            for palavra in set(_MARCA_PALAVRA.sub(" ", sem_acento(doc)).split())
        )
        return {p: math.log((1 + n) / (1 + c)) + 1 for p, c in contagem.items()}

    def _df(self, termo: str) -> int:
        """Em quantos artigos aparece o termo ou qualquer equivalente pt/en dele."""
        if termo not in self._cache_df:
            variantes = {termo} | equivalentes(termo)
            self._cache_df[termo] = sum(
                1 for palavras, texto in zip(self._palavras_doc, self._textos_norm)
                if any((v in palavras) if " " not in v else (v in texto) for v in variantes)
            )
        return self._cache_df[termo]

    def so_tema(self, consulta: str) -> bool:
        """A mensagem é só um tema que a base conhece? ("depressão", "cárie infantil")

        Verdadeiro quando, tiradas as palavras de enchimento e as funcionais, sobram de 1 a
        MAX_TERMOS_TEMA palavras e TODAS são tema da base: aparecem em pelo menos
        MIN_ARTIGOS_TEMA artigos (ou têm equivalente pt/en neles) e não são vocabulário de
        outra ação do bot (`TERMOS_DO_SISTEMA`). Vale também para palavras curtas: "faz" em
        "faz minha introdução sobre cárie" aparece em um só artigo, logo não é tema e a
        mensagem fica com o classificador. É a evidência de que o usuário buscou um assunto,
        que o classificador não tem para um substantivo solto.
        """
        palavras = _MARCA_PALAVRA.sub(" ", sem_acento(consulta)).split()
        conteudo = [t for t in palavras if t not in GENERICAS and t not in _FUNCIONAIS]
        if not conteudo or len(conteudo) > MAX_TERMOS_TEMA:
            return False
        return all(t not in TERMOS_DO_SISTEMA and self._df(t) >= MIN_ARTIGOS_TEMA for t in conteudo)

    def _peso(self, termo: str) -> float:
        """Raridade do conceito: idf calculado sobre os artigos que têm QUALQUER variante pt/en.

        Antes era o maior idf entre as variantes, e a forma em português (que só existe nos
        40 artigos em pt) inflava o peso de conceitos comuns: "crianças" pesava como se fosse
        raro e um artigo com "crianças" + "transtornos", sem "ansiedade", passava da
        cobertura mínima. Para termo sem equivalente o valor é o mesmo de antes.

        Termo que não existe no vocabulário recebe o idf máximo: é o mais discriminante
        possível, e a similaridade (que devolve 0) é quem vai barrar.
        """
        if termo not in self._cache_peso:
            df = self._df(termo)
            n = len(self.artigos) or 1
            self._cache_peso[termo] = (
                math.log((1 + n) / (1 + df)) + 1 if df
                else self._faixa_idf[1] or 1.0
            )
        return self._cache_peso[termo]

    @staticmethod
    def _contem(alvo: str, palavra: str) -> bool:
        """True se `palavra` aparece no texto como palavra inteira ou flexão simples.

        "quântica" precisa casar com "quantica"/"quanticas", **não** com "quantitative":
        o radical de 5 letras (`quant`) casava com qualquer início de palavra e um artigo
        de Psicologia que diz "quantitative methods" virava 0,5 de cobertura para a busca
        de computação quântica. Antes eu cortava a palavra; agora o casamento é: termo
        inteiro, termo + flexão, ou um equivalente pt/en declarado em ALIASES.
        """
        def palavra_inteira(raiz: str, sufixos: str = "") -> bool:
            return bool(re.search(rf"(?<![0-9a-z]){re.escape(raiz)}{sufixos}(?![0-9a-z])", alvo))

        # Flexão de número/gênero: "universitarios" cobre "universitario"; "carie" cobre "caries".
        return (
            palavra_inteira(palavra, "(?:s|es|a|o|as|os)?")
            or (palavra.endswith(("a", "o")) and palavra_inteira(palavra[:-1]))
        )

    def _conceitos(self, termos: set[str]) -> tuple[list[tuple[str, ...]], set[str]]:
        """Separa os termos da pergunta em conceitos compostos e termos soltos.

        "aprendizado de máquina" e "segurança da informação" são **um** conceito: exigir os
        dois termos juntos evita que um artigo de Psicologia sobre "processos de ensino e
        aprendizagem" cubra a busca por aprendizado de máquina.
        """
        usados: set[str] = set()
        conceitos: list[tuple[str, ...]] = []
        for conceito in CONCEITOS:
            if all(c in termos for c in conceito):
                conceitos.append(conceito)
                usados.update(conceito)
        return conceitos, termos - usados

    def _cobertura(self, consulta: str, artigo: dict, termos: set[str]) -> float:
        """Quanto da informação da pergunta o artigo cobre, pesando os termos por raridade.

        O peso é o idf de cada termo normalizado para 0–1 **antes** de somar: assim casar
        um termo raro ("clareamento", em 13 dos 247 artigos) vale quase 1,0 e casar um
        termo comum ("dental", em quase metade da base de Odontologia) vale perto de 0.
        Conceitos compostos ("aprendizado de máquina") só contam quando aparecem inteiros.
        """
        if not termos:
            return 1.0
        alvo = sem_acento(" ".join([
            artigo.get("titulo") or "",
            artigo.get("resumo") or "",
            " ".join(artigo.get("palavras_chave") or []),
        ]))

        def presente(termo: str) -> bool:
            return any(self._contem(alvo, v) for v in ({termo} | equivalentes(termo)))

        conceitos, soltos = self._conceitos(termos)

        # Ordem fixa na soma: os termos vêm de um `set`, e somar float em ordem diferente
        # dá resultado diferente (a ordem do set muda a cada processo, por hash
        # randomization). Sem isso, um artigo no limite do limiar entra numa rodada e fica
        # de fora na outra — a Precisão@5 do relatório variava entre 0,657 e 0,743.
        itens = [(conceito, sum(self._peso_normalizado(t) for t in sorted(conceito)))
                 for conceito in sorted(conceitos)]
        for termo in sorted(soltos):
            itens.append(((termo,), self._peso_normalizado(termo)))

        total = sum(peso for _, peso in itens)
        if not total:
            return 1.0
        coberto = sum(peso for conceito, peso in itens if all(presente(t) for t in conceito))

        # Arredonda o valor que decide o corte, para que ruído de ponto flutuante não
        # troque a decisão de incluir ou não o artigo.
        return round(coberto / total, _PRECISAO_COBERTURA)

    def _peso_normalizado(self, termo: str) -> float:
        """Idf do termo reescalado para 0–1 dentro do vocabulário da base."""
        minimo, maximo = self._faixa_idf
        if maximo <= minimo:
            return 1.0
        return (self._peso(termo) - minimo) / (maximo - minimo)

    @property
    def pronto(self) -> bool:
        return self._vetorizador is not None and bool(self.artigos)

    # -------------------------------------------------------- indexação
    def _campo_do_periodico(self, artigo: dict, campo: str) -> list[str]:
        """Valor de `campo` no primeiro periódico curado do artigo (por ISSN) que o tenha."""
        for issn in artigo.get("issn") or []:
            valor = (self.periodicos_por_issn.get(issn) or {}).get(campo)
            if valor:
                return list(valor)
        return []

    def indexacao(self, artigo: dict) -> list[str]:
        return self._campo_do_periodico(artigo, "indexacao")

    def revisao(self, artigo: dict) -> str | None:
        # `revisao` é uma lista de rótulos do DOAJ; o mais forte vem primeiro
        rotulos = self._campo_do_periodico(artigo, "revisao")
        return next((r for r in ("dupla_cega", "pares", "editorial") if r in rotulos), None)

    # -------------------------------------------------------- busca
    def _consulta_expandida(self, consulta: str, termos: set[str]) -> str:
        """Consulta de busca com os equivalentes pt/en dos termos temáticos.

        A base é majoritariamente em inglês e as perguntas simuladas são em português:
        sem expandir, "clareamento dental" não casa com "dental bleaching" e a busca
        devolve o que tem a palavra literal no título, não o que trata do assunto.
        """
        acrescimos = []
        for termo in sorted(termos):
            acrescimos += sorted(equivalentes(termo))
        return " ".join([consulta, *acrescimos])

    def _bonus(self, artigo: dict, area: str | None, ano_limite: int) -> tuple[float, list[str]]:
        """Bônus de curadoria (revisão, indexação, ano, área) e os motivos que o justificam."""
        bonus, motivos = 0.0, []

        revisao = self.revisao(artigo)
        if BONUS_REVISAO.get(revisao):
            bonus += BONUS_REVISAO[revisao]
            motivos.append(
                "revisão por pares em dupla cega" if revisao == "dupla_cega" else "revisado por pares"
            )

        indexadores = self.indexacao(artigo)
        soma_ind = min(sum(BONUS_INDEXACAO.get(x, 0) for x in indexadores), BONUS_INDEXACAO_MAX)
        if soma_ind:
            bonus += soma_ind
            motivos.append("indexado em " + ", ".join(sorted(set(indexadores))))

        if artigo.get("ano") and artigo["ano"] >= ano_limite:
            bonus += BONUS_ANO_RECENTE
            motivos.append(f"publicado em {artigo['ano']}")

        if area and artigo.get("area") == area:
            bonus += BONUS_MESMA_AREA
            motivos.append(f"da área de {area}")
        return bonus, motivos

    def buscar(self, consulta: str, k: int = TOP_K, area: str | None = None,
               cobertura_minima: float = COBERTURA_MINIMA) -> list[Candidato]:
        if not self.pronto:
            return []
        termos = self._termos_consulta(consulta)
        vetor = self._vetorizador.transform([self._consulta_expandida(consulta, termos)])
        similaridades = cosine_similarity(vetor, self._matriz)[0]
        ano_limite = max((a.get("ano") or 0) for a in self.artigos) - 2

        candidatos: list[Candidato] = []
        for i, artigo in enumerate(self.artigos):
            sim = float(similaridades[i])
            if sim <= 0:
                continue
            cobertura = self._cobertura(consulta, artigo, termos)
            # Guarda temática: sem cobrir os termos que identificam o tema, a similaridade
            # vem só de palavras genéricas ("artigo", "estudo") e não deve recomendar.
            if cobertura < cobertura_minima:
                continue
            # O bônus de curadoria é desempate, não relevância. Sem esta guarda ele somava
            # por cima de uma similaridade quase nula: um artigo de Psicologia que não tem
            # nenhuma palavra da pergunta chegava a 0,14 só por ser indexado e recente, e
            # passava do limiar de score.
            if cobertura <= 0:
                continue
            bonus, motivos = self._bonus(artigo, area, ano_limite)
            score = min(sim + bonus, 1.0)
            candidatos.append(Candidato(artigo, score, sim, motivos, cobertura))

        # Cobertura parcial só preenche a lista quando faltam artigos completos: "depressão em
        # adolescentes" não deve devolver artigo que só fala de adolescentes se já há ao
        # menos MIN_COBERTURA_COMPLETA artigos que tratam dos dois termos.
        completos = [c for c in candidatos if c.cobertura >= 1.0]
        if len(completos) >= MIN_COBERTURA_COMPLETA:
            candidatos = completos
        candidatos.sort(key=lambda c: (-c.score, -(c.artigo.get("ano") or 0), c.artigo.get("doi") or ""))
        return candidatos[:k]

    # -------------------------------------------------------- utilidades
    def por_id(self, artigo_id: str) -> dict | None:
        return next((a for a in self.artigos if a.get("id") == artigo_id), None)

    def periodicos(self) -> list[dict]:
        return list(self.periodicos_por_issn.values())

    def buscar_periodico(self, texto: str) -> list[dict]:
        """Casa o nome ou o ISSN citado pelo usuário com a lista curada."""
        alvo = sem_acento(texto)
        alvo_limpo = "".join(ch for ch in alvo if ch.isalnum() or ch == " ")
        achados = []
        for p in self.periodicos():
            titulo = sem_acento(p.get("titulo") or "")
            if titulo and (titulo in alvo_limpo or all(w in alvo_limpo for w in titulo.split()[:3])):
                achados.append(p)
                continue
            if any(issn.replace("-", "") in alvo_limpo.replace("-", "") for issn in p.get("issn", [])):
                achados.append(p)
        return achados

    def detetar_area(self, texto: str) -> str | None:
        alvo = sem_acento(texto)
        pontuacao = {
            área: sum(1 for pista in lista if pista in alvo) for área, lista in PISTAS_AREA.items()
        }
        melhor = max(pontuacao, key=lambda a: pontuacao[a])
        return melhor if pontuacao[melhor] else None

    def estatisticas(self) -> dict:
        anos = [a["ano"] for a in self.artigos if a.get("ano")]
        return {
            "artigos": len(self.artigos),
            "periodicos": len(self.periodicos()),
            "anos": [min(anos), max(anos)] if anos else [],
            "areas": sorted({a.get("area") for a in self.artigos if a.get("area")}),
        }


def normalizar_score(score: float) -> float:
    """Arredonda o score exibido sem perder a ordenação."""
    return round(math.floor(score * 1000) / 1000, 3)


_cache: Motor | None = None


def obter() -> Motor:
    global _cache
    if _cache is None:
        _cache = Motor()
    return _cache

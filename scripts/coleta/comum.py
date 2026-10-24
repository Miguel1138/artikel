"""Funções compartilhadas pelos clientes de coleta."""
import html
import json
import re
import time
import unicodedata
from datetime import date

import requests

from config_coleta import AREA_LCC, AREA_LCC_EXCLUI, AREA_WOS, AREA_WOS_EXCLUI, DIR_RAW, MAILTO

_sessao = requests.Session()
_sessao.headers["User-Agent"] = (
    f"Artikel/0.1 (projeto academico A3; mailto:{MAILTO})" if MAILTO
    else "Artikel/0.1 (projeto academico A3)"
)

# Esquema da base (arquitetura, seção 5).
CAMPOS = ["id", "doi", "titulo", "autores", "ano", "periodico", "issn", "volume",
          "numero", "paginas", "resumo", "palavras_chave", "idioma", "licenca",
          "area", "fonte", "url", "data_coleta"]
VAZIO = (None, "", [])


def get_json(url, params=None, tentativas=4, pausa=1.0):
    """GET com nova tentativa em 429/5xx. Retorna None em 404.

    Alguns serviços (DOAJ) respondem `Content-Type: application/json;charset=utf-8`, que
    `r.json()` recusa por causa do charset. Por isso o parsing é feito do texto.
    """
    for i in range(tentativas):
        try:
            r = _sessao.get(url, params=params, timeout=30)
        except requests.RequestException:
            if i == tentativas - 1:
                raise
            time.sleep(pausa * 2 ** i)
            continue
        if r.status_code == 404:
            return None
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(pausa * 2 ** i)
            continue
        if r.status_code >= 400:
            # A mensagem da API diz o parâmetro inválido; sem ela o erro fica opaco.
            raise requests.HTTPError(f"{r.status_code} em {r.url}\n{r.text[:500]}", response=r)
        try:
            return json.loads(r.text)
        except ValueError:
            return None
    raise RuntimeError(f"Falha após {tentativas} tentativas: {url}")


# --- Área do periódico -------------------------------------------------
def lcc_da_area(area, codigos):
    """True se algum código LCC do periódico começa com um prefixo da área (e não de exclusão)."""
    exclui = AREA_LCC_EXCLUI.get(area, ())
    return any(c.startswith(p) and not c.startswith(exclui)
               for c in codigos for p in AREA_LCC[area])


def wos_da_area(area, areas_wos):
    """True se alguma área WoS do periódico contém um trecho da área (e nenhum de exclusão)."""
    exclui = AREA_WOS_EXCLUI.get(area, ())
    return any(alvo in a and not any(x in a for x in exclui)
               for a in areas_wos for alvo in AREA_WOS[area])


# --- data/raw ----------------------------------------------------------
def sem_acento(t):
    return "".join(c for c in unicodedata.normalize("NFKD", t) if not unicodedata.combining(c))


def slug(t):
    return re.sub(r"[^a-z0-9]+", "_", sem_acento(t).lower()).strip("_")[:80]


def salvar_raw(fonte, nome, dados):
    pasta = DIR_RAW / fonte
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / f"{slug(nome)}.json").write_text(
        json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def ler_raw(fonte, nome):
    arq = DIR_RAW / fonte / f"{slug(nome)}.json"
    return json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else None


# --- Normalização ------------------------------------------------------
def normalizar_doi(doi):
    if not doi:
        return None
    doi = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", doi.strip().lower())
    return doi or None


_RE_CC_URL = re.compile(r"creativecommons\.org/licenses/([a-z\-]+)/")


def normalizar_licenca(texto):
    """URL ou rótulo CC -> 'cc-by', 'cc-by-nc', 'cc0'... ou None."""
    if not texto:
        return None
    t = texto.lower().strip()
    m = _RE_CC_URL.search(t)
    if m:
        return "cc-" + m.group(1)
    if "publicdomain/zero" in t or t.replace(" ", "").replace("-", "") == "cc0":
        return "cc0"
    t = re.sub(r"[\s_]+", "-", t)
    if t.startswith("by"):          # SciELO usa 'by/4.0'
        t = "cc-" + t
    m = re.match(r"^cc-(by(?:-(?:nc|sa|nd))*)", t)
    return "cc-" + m.group(1) if m else None


def limpar_texto(t):
    """Remove tags (JATS/HTML), entidades e o rótulo 'Abstract'/'Resumo'."""
    if not t:
        return None
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"^(abstract|resumo)[:.\s]+", "", t, flags=re.I)
    return t or None


_IDIOMAS = {"en": "en", "eng": "en", "english": "en",
            "pt": "pt", "por": "pt", "pt-br": "pt", "portuguese": "pt",
            "es": "es", "spa": "es", "spanish": "es"}

# Palavras que só aparecem em português em título/resumo científico.
_MARCAS_PT = (" de ", " da ", " do ", " para ", " com ", " dos ", " das ", " na ", " no ",
              " uma ", " sobre ", " entre ", "ção ", "ções ", "ção.", "não ")
_MARCAS_EN = (" of ", " the ", " and ", " for ", " with ", " from ", " this ", " study ",
              " were ", " was ", " is ", " are ", " between ")


def normalizar_idioma(codigo):
    return _IDIOMAS.get((codigo or "").strip().lower())


def detetar_idioma(titulo, resumo=None):
    """pt/en pelo texto, porque o Crossref não informa `language`.

    Sem isso, artigos em português seriam descartados pelo filtro de idioma do pipeline —
    e a base ficaria só em inglês, contrariando a premissa de equilíbrio de idioma.
    """
    amostra = " " + " ".join((titulo or "", resumo or "")).lower() + " "
    if not amostra.strip():
        return None
    if any(c in amostra for c in "ãõçáéíóúâêôà"):
        return "pt"
    pt = sum(amostra.count(m) for m in _MARCAS_PT)
    en = sum(amostra.count(m) for m in _MARCAS_EN)
    if pt > en:
        return "pt"
    if en > pt:
        return "en"
    return None


def novo_registro(fonte):
    """Registro vazio no esquema da base. Campos com '_' são internos e não vão para o JSON final."""
    r = {c: None for c in CAMPOS}
    r.update(autores=[], palavras_chave=[], issn=[], fonte=fonte, _data=None)
    return r


def hoje():
    return date.today().isoformat()
"""Funções compartilhadas pelos clientes de coleta."""
import html
import json
import re
import time
import unicodedata
from datetime import date

import requests

from config_coleta import DIR_RAW, MAILTO

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
    """GET com nova tentativa em 429/5xx. Retorna None em 404."""
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
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"Falha após {tentativas} tentativas: {url}")


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
            "pt": "pt", "por": "pt", "pt-br": "pt", "portuguese": "pt"}


def normalizar_idioma(codigo):
    return _IDIOMAS.get((codigo or "").strip().lower())


def novo_registro(fonte):
    """Registro vazio no esquema da base. Campos com '_' são internos e não vão para o JSON final."""
    r = {c: None for c in CAMPOS}
    r.update(autores=[], palavras_chave=[], issn=[], fonte=fonte, _data=None, _medline=False)
    return r


def hoje():
    return date.today().isoformat()

"""Cliente DOAJ: indexação e assunto (LCC) do periódico por ISSN.
Base da intenção avaliar_fonte (periodicos.json)."""
from functools import lru_cache
from urllib.parse import quote

from comum import get_json, ler_raw, salvar_raw

BASE = "https://doaj.org/api/search/journals/"  # a consulta vai no caminho da URL


@lru_cache(maxsize=None)
def periodico_por_issn(issn):
    """Dados normalizados do periódico, ou None se não está no DOAJ."""
    dados = ler_raw("doaj", issn)
    if dados is None:
        dados = get_json(BASE + quote(f"issn:{issn}")) or {}
        salvar_raw("doaj", issn, dados)
    resultados = dados.get("results") or []
    return normalizar(resultados[0]["bibjson"]) if resultados else None


def normalizar(b):
    assuntos = b.get("subject", [])
    return {
        "titulo": b.get("title"),
        "issn": [i for i in (b.get("pissn"), b.get("eissn")) if i],
        "assuntos": [s.get("term") for s in assuntos],
        "lcc": [s.get("code") for s in assuntos if s.get("scheme") == "LCC"],
        "revisao": (b.get("editorial") or {}).get("review_process", []),
        "licencas": [l.get("type") for l in b.get("license", [])],
        "url": (b.get("ref") or {}).get("journal"),
    }

"""Indexação MEDLINE do periódico por ISSN, via NLM Catalog (NCBI E-utilities).
Sem chave de API (limite de 3 requisições/s). Resultado em cache em data/raw/medline."""
import time
from functools import lru_cache

from comum import get_json, ler_raw, salvar_raw

ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"


@lru_cache(maxsize=None)
def indexado(issn):
    """True se o periódico está atualmente indexado no MEDLINE."""
    dados = ler_raw("medline", issn)
    if dados is None:
        time.sleep(0.35)  # respeita o limite sem chave
        dados = get_json(ESEARCH, {"db": "nlmcatalog", "retmode": "json",
                                   "term": f"{issn}[issn] AND currentlyindexed[All]"}) or {}
        salvar_raw("medline", issn, dados)
    return int(dados.get("esearchresult", {}).get("count", 0)) > 0
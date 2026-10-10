"""Cliente Europe PMC (complemento para Odontologia e Psicologia)."""
from comum import (get_json, limpar_texto, normalizar_doi, normalizar_idioma,
                   normalizar_licenca, novo_registro)
from config_coleta import ANO_FIM, ANO_INICIO, CANDIDATOS_POR_CONSULTA

BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


def buscar(consulta, limite=CANDIDATOS_POR_CONSULTA):
    """Itens brutos mais recentes, já filtrados por período, DOI, licença e idioma."""
    query = (f"({consulta}) AND PUB_YEAR:[{ANO_INICIO} TO {ANO_FIM}] "
             'AND HAS_DOI:y AND LICENSE:"cc by" AND (LANG:eng OR LANG:por)')
    dados = get_json(BASE, {"query": query, "format": "json", "resultType": "core",
                            "pageSize": limite, "sort": "P_PDATE_D desc"})
    return (dados or {}).get("resultList", {}).get("result", [])


def _autores(item):
    autores = []
    for a in (item.get("authorList") or {}).get("author", []):
        if a.get("lastName"):
            autores.append({"sobrenome": a["lastName"], "nome": a.get("firstName", "")})
        elif a.get("collectiveName"):
            autores.append({"sobrenome": a["collectiveName"], "nome": ""})
    return autores


def normalizar(item):
    r = novo_registro("europepmc")
    info = item.get("journalInfo") or {}
    revista = info.get("journal") or {}
    doi = normalizar_doi(item.get("doi"))
    titulo = limpar_texto(item.get("title"))
    r.update(
        doi=doi,
        titulo=titulo.rstrip(".") if titulo else None,
        autores=_autores(item),
        ano=int(item["pubYear"]) if item.get("pubYear") else None,
        _data=item.get("firstPublicationDate"),
        periodico=revista.get("title"),
        issn=[i for i in (revista.get("issn"), revista.get("essn")) if i],
        volume=info.get("volume"),
        numero=info.get("issue"),
        paginas=item.get("pageInfo"),
        resumo=limpar_texto(item.get("abstractText")),
        palavras_chave=(item.get("keywordList") or {}).get("keyword", []),
        idioma=normalizar_idioma(item.get("language")),
        licenca=normalizar_licenca(item.get("license")),
        url=f"https://doi.org/{doi}" if doi else None,
        # VERIFICAR: source == "MED" indica registro PubMed, que não é o mesmo que
        # indexação MEDLINE. Trocar pelo campo exato antes de usar como critério.
        _medline=item.get("source") == "MED",
    )
    return r

"""Cliente Europe PMC (complemento para Odontologia, Psicologia, Medicina e Biologia)."""
from comum import (get_json, limpar_texto, normalizar_doi, normalizar_idioma,
                   normalizar_licenca, novo_registro)
from config_coleta import ANO_FIM, ANO_INICIO, CANDIDATOS_POR_CONSULTA

BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


def buscar(consulta, limite=CANDIDATOS_POR_CONSULTA):
    """Itens brutos, já filtrados por período, DOI, licença e idioma, divididos por ano.

    Uma consulta só com `PUB_YEAR:[ini TO fim]` volta com quase tudo do ano corrente, com ou
    sem `sort`, e a janela de 10 anos não chegaria ao pipeline. Por isso há uma consulta
    por ano, cada uma com a sua fatia do `limite`.
    """
    anos = range(ANO_INICIO, ANO_FIM + 1)
    por_ano = -(-limite // len(anos))
    itens = []
    for ano in anos:
        query = (f"({consulta}) AND PUB_YEAR:{ano} "
                 'AND HAS_DOI:y AND (LICENSE:"cc by" OR LICENSE:"cc0") AND (LANG:eng OR LANG:por)')
        dados = get_json(BASE, {"query": query, "format": "json", "resultType": "core",
                                "pageSize": por_ano})
        itens += (dados or {}).get("resultList", {}).get("result", [])
    return itens


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
    )
    return r
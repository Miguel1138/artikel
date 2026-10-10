"""Cliente Crossref: busca por consulta e validação/enriquecimento por DOI.
Fonte principal; prevalece em conflitos de campos (decisão do Marco 2)."""
from urllib.parse import quote

from comum import (get_json, limpar_texto, normalizar_doi, normalizar_idioma,
                   normalizar_licenca, novo_registro)
from config_coleta import ANO_FIM, ANO_INICIO, CANDIDATOS_POR_CONSULTA, MAILTO

BASE = "https://api.crossref.org/works"
SELECT = "DOI,title,author,published,container-title,ISSN,volume,issue,page,abstract,license,language,URL"


def _params(extra):
    p = dict(extra)
    if MAILTO:
        p["mailto"] = MAILTO
    return p


def buscar(consulta, limite=CANDIDATOS_POR_CONSULTA):
    """Itens brutos mais recentes que casam com a consulta, já filtrados por período e licença."""
    dados = get_json(BASE, _params({
        "query.bibliographic": consulta,
        "filter": (f"from-pub-date:{ANO_INICIO}-01-01,until-pub-date:{ANO_FIM}-12-31,"
                   "type:journal-article,has-license:true"),
        "sort": "published", "order": "desc",
        "rows": limite, "select": SELECT,
    }))
    return dados["message"]["items"] if dados else []


def por_doi(doi):
    """Item bruto do DOI, ou None se o DOI não existe no Crossref."""
    dados = get_json(f"{BASE}/{quote(doi, safe='/')}", _params({}))
    return dados["message"] if dados else None


def _data(item):
    partes = ((item.get("published") or {}).get("date-parts") or [[None]])[0]
    if not partes or partes[0] is None:
        return None, None
    return partes[0], "-".join(f"{p:02d}" for p in partes)


def _licenca(item):
    # Versão publicada (VoR) primeiro.
    for lic in sorted(item.get("license") or [], key=lambda l: l.get("content-version") != "vor"):
        n = normalizar_licenca(lic.get("URL"))
        if n:
            return n
    return None


def _autores(item):
    autores = []
    for a in item.get("author", []):
        if a.get("family"):
            autores.append({"sobrenome": a["family"], "nome": a.get("given", "")})
        elif a.get("name"):  # autor institucional
            autores.append({"sobrenome": a["name"], "nome": ""})
    return autores


def normalizar(item):
    r = novo_registro("crossref")
    ano, data = _data(item)
    r.update(
        doi=normalizar_doi(item.get("DOI")),
        titulo=limpar_texto((item.get("title") or [None])[0]),
        autores=_autores(item),
        ano=ano, _data=data,
        periodico=(item.get("container-title") or [None])[0],
        issn=item.get("ISSN", []),
        volume=item.get("volume"),
        numero=item.get("issue"),
        paginas=item.get("page"),
        resumo=limpar_texto(item.get("abstract")),
        idioma=normalizar_idioma(item.get("language")),
        licenca=_licenca(item),
        url=item.get("URL"),
    )
    return r

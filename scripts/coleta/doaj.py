"""Cliente DOAJ: indexação e assunto (LCC) do periódico por ISSN, e busca de artigos.

Duas funções:

1. `periodico_por_issn` — base da intenção `avaliar_fonte` (alimenta `periodicos.json`);
2. `buscar_artigos` — **fonte complementar de artigos para Computação**. O Crossref cobre
   bem saúde, mas em Computação devolve resultados de áreas vizinhas que não passam pelo
   filtro temático; o DOAJ indexa por assunto LCC e permite buscar no resumo, o que
   resolve o buraco da área de Computação no recorte do Marco 2.
"""
from functools import lru_cache
from urllib.parse import quote

from comum import (get_json, ler_raw, limpar_texto, normalizar_doi, normalizar_idioma,
                   normalizar_licenca, novo_registro, salvar_raw)
from config_coleta import ANO_FIM, ANO_INICIO, CANDIDATOS_POR_CONSULTA, LICENCAS_ACEITAS

BASE = "https://doaj.org/api/search/journals/"   # a consulta vai no caminho da URL
BASE_ARTIGOS = "https://doaj.org/api/search/articles/"


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
    licencas = [l.get("type") for l in (b.get("license") or [])]
    return {
        "titulo": b.get("title"),
        "issn": [i for i in (b.get("pissn"), b.get("eissn")) if i],
        "assuntos": [s.get("term") for s in assuntos],
        "lcc": [s.get("code") for s in assuntos if s.get("scheme") == "LCC"],
        "revisao": (b.get("editorial") or {}).get("review_process", []),
        "licencas": licencas,
        "licenca": proxima(licencas),
        "url": (b.get("ref") or {}).get("journal"),
    }


# --------------------------------------------------------------- artigos
def buscar_artigos(consulta, limite=CANDIDATOS_POR_CONSULTA):
    """Artigos do DOAJ que casam com a consulta (sintaxe Elasticsearch do DOAJ).

    O índice do DOAJ traz `bibjson.abstract` quase sempre preenchido, o que é o que a
    recuperação do Artikel usa para casar tema.
    """
    url = BASE_ARTIGOS + quote(consulta, safe="")
    dados = get_json(url, {"pageSize": limite}) or {}
    return dados.get("results", [])


def _autores(b):
    autores = []
    for a in b.get("author") or []:
        nome = (a.get("name") or "").strip()
        if not nome:
            continue
        partes = nome.rsplit(" ", 1)
        if len(partes) == 2:
            autores.append({"sobrenome": partes[1], "nome": partes[0]})
        else:
            autores.append({"sobrenome": nome, "nome": ""})
    return autores


def _licenca(b):
    tipos = [l.get("type") for l in (b.get("license") or []) if l.get("type")]
    return proxima(tipos)


def proxima(tipos):
    """Primeira licença da lista que o recorte aceita (CC-BY ou CC0)."""
    for tipo in tipos:
        normalizada = normalizar_licenca(tipo)
        if normalizada in LICENCAS_ACEITAS:
            return normalizada
    return None


def _link(b):
    for l in b.get("link") or []:
        if l.get("type") == "fulltext" and l.get("url"):
            return l["url"]
    return None


def normalizar_artigo(item):
    """Item do Article Search -> registro do esquema da base.

    O Article Search do DOAJ **não devolve a licença** do periódico (só `journal.title`,
    ISSNs, volume, número e idioma). Por isso a licença é preenchida depois, por
    `aplicar_licenca`, a partir do cadastro do periódico — sem isso todos os artigos
    entrariam sem licença e o filtro do recorte os descartaria.
    """
    b = item.get("bibjson") or {}
    r = novo_registro("doaj")
    revista = b.get("journal") or {}
    ano = b.get("year")
    try:
        ano = int(str(ano)[:4])
    except (TypeError, ValueError):
        ano = None
    doi = next((i["id"] for i in b.get("identifier") or [] if i.get("type") == "doi"), None)
    idiomas = revista.get("language") or []
    r.update(
        doi=normalizar_doi(doi),
        titulo=limpar_texto(b.get("title")),
        autores=_autores(b),
        ano=ano,
        _data=f"{ano}-01-01" if ano else None,
        periodico=revista.get("title"),
        issn=revista.get("issns", []),
        volume=revista.get("volume"),
        numero=revista.get("number"),
        paginas=b.get("start_page") if b.get("start_page") not in (None, "n/a") else None,
        resumo=limpar_texto(b.get("abstract")),
        palavras_chave=b.get("keywords") or [],
        idioma=normalizar_idioma((idiomas or [None])[0]),
        licenca=_licenca(b),
        url=_link(b) or (f"https://doi.org/{doi}" if doi else None),
    )
    return r


def _indexar_por_issn(lista):
    """Lista de periódicos -> dicionário por ISSN.

    Cada periódico tem **uma lista** de ISSNs (impresso e eletrônico), então o índice
    precisa de um laço interno: usar `p["issn"]` direto como chave levanta
    `TypeError: unhashable type: 'list'` sempre que o resultado vem do cache.
    """
    indice = {}
    for periodico in lista:
        for issn in periodico.get("issn") or []:
            indice[issn] = periodico
    return indice


def periodicos_computacao_cc():
    """Periódicos do DOAJ de Ciência da Computação cujo cadastro tem licença aceita.

    Uma requisição cobre os 314 periódicos do assunto, em vez de uma consulta por artigo.
    O resultado fica em cache e serve para filtrar (e licenciar) os artigos do DOAJ sem
    gastar centenas de chamadas.
    """
    chave = "periodicos_computacao_cc"
    cache = ler_raw("doaj", chave)
    if cache is not None:
        return _indexar_por_issn(cache)

    consulta = 'bibjson.subject.term:"Electronic computers. Computer science"'
    url = BASE + quote(consulta, safe="")
    dados = get_json(url, {"pageSize": 400}) or {}
    lista = []
    for item in dados.get("results") or []:
        b = item.get("bibjson") or {}
        licenca = next((normalizar_licenca(t) for t in
                        (l.get("type") for l in (b.get("license") or []))
                        if normalizar_licenca(t) in LICENCAS_ACEITAS), None)
        if not licenca:
            continue
        lista.append({
            "titulo": b.get("title"),
            "issn": [i for i in (b.get("pissn"), b.get("eissn")) if i],
            "licenca": licenca,
            "revisao": (b.get("editorial") or {}).get("review_process", []),
            "assuntos": [s.get("term") for s in (b.get("subject") or [])],
            "lcc": [s.get("code") for s in (b.get("subject") or [])
                    if s.get("scheme") == "LCC"],
            "url": (b.get("ref") or {}).get("journal"),
        })
    salvar_raw("doaj", chave, lista)
    return _indexar_por_issn(lista)

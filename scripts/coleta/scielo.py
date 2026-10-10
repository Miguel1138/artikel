"""Cliente SciELO Brasil (ArticleMeta).

O ArticleMeta não tem busca por termo. Estratégia:
  1. listar os periódicos SciELO da área (pela área WoS do periódico);
  2. baixar os artigos do período de cada periódico;
  3. o filtro temático pelas sementes acontece no pipeline.
É a fonte mais cara em requisições: tudo fica em cache em data/raw/scielo.
VERIFICAR nomes de atributos do xylose contra a coleção do Insomnia.
"""
from comum import (get_json, ler_raw, limpar_texto, normalizar_doi, normalizar_idioma,
                   normalizar_licenca, novo_registro, salvar_raw)
from config_coleta import ANO_FIM, ANO_INICIO, AREA_WOS, MAX_ARTIGOS_POR_PERIODICO

from xylose.scielodocument import Article, Journal

BASE = "http://articlemeta.scielo.org/api/v1"
COLECAO = "scl"
LOTE = 1000


def _get(obj, nome):
    """Lê atributo ou método do xylose sem quebrar quando o campo falta."""
    try:
        v = getattr(obj, nome)
        return v() if callable(v) else v
    except Exception:
        return None


def _identificadores(tipo, **filtros):
    offset = 0
    while True:
        dados = get_json(f"{BASE}/{tipo}/identifiers/",
                         {"collection": COLECAO, "offset": offset, **filtros}) or {}
        objetos = dados.get("objects", [])
        yield from objetos
        offset += LOTE
        if not objetos or offset >= dados.get("meta", {}).get("total", 0):
            return


def periodicos(area):
    """Periódicos SciELO Brasil da área (cache em data/raw/scielo)."""
    nome = f"periodicos_{area}"
    cache = ler_raw("scielo", nome)
    if cache is not None:
        return cache
    lista = []
    for obj in _identificadores("journal"):
        bruto = get_json(f"{BASE}/journal/", {"collection": COLECAO, "issn": obj["code"]})
        if not bruto:
            continue
        j = Journal(bruto[0] if isinstance(bruto, list) else bruto)
        areas = [a.upper() for a in (_get(j, "wos_subject_areas") or [])]
        if any(alvo in a for a in areas for alvo in AREA_WOS[area]):
            lista.append({
                "titulo": _get(j, "title"),
                "issn": [i for i in (_get(j, "print_issn"), _get(j, "electronic_issn")) if i],
                "areas_wos": areas,
            })
    salvar_raw("scielo", nome, lista)
    return lista


def artigos(issn, maximo=MAX_ARTIGOS_POR_PERIODICO):
    """Artigos brutos do periódico no período, mais recentes primeiro."""
    # Atenção: from/until do ArticleMeta filtram data de processamento, não de publicação.
    ids = list(_identificadores("article", issn=issn,
                                **{"from": f"{ANO_INICIO}-01-01", "until": f"{ANO_FIM}-12-31"}))
    ids.sort(key=lambda o: o.get("processing_date", ""), reverse=True)
    for obj in ids[:maximo]:
        pid = obj["code"]
        bruto = ler_raw("scielo", pid)
        if bruto is None:
            bruto = get_json(f"{BASE}/article/", {"collection": COLECAO, "code": pid, "format": "json"})
            if bruto:
                salvar_raw("scielo", pid, bruto)
        if bruto:
            yield bruto


def normalizar(bruto):
    a = Article(bruto)
    r = novo_registro("scielo")
    lingua = _get(a, "original_language")
    data = _get(a, "publication_date")  # 'AAAA-MM-DD' ou 'AAAA'
    revista = _get(a, "journal")
    permissoes = _get(a, "permissions") or {}
    paginas = "-".join(p for p in (_get(a, "start_page"), _get(a, "end_page")) if p)
    r.update(
        doi=normalizar_doi(_get(a, "doi")),
        titulo=limpar_texto(_get(a, "original_title")),
        autores=[{"sobrenome": x.get("surname", ""), "nome": x.get("given_names", "")}
                 for x in (_get(a, "authors") or [])],
        ano=int(data[:4]) if data else None,
        _data=data,
        periodico=_get(revista, "title"),
        issn=[i for i in (_get(revista, "print_issn"), _get(revista, "electronic_issn")) if i],
        volume=_get(a, "volume"),
        numero=_get(a, "issue"),
        paginas=paginas or None,
        resumo=limpar_texto(_get(a, "original_abstract")),
        palavras_chave=(_get(a, "keywords") or {}).get(lingua, []),
        idioma=normalizar_idioma(lingua),
        licenca=normalizar_licenca(permissoes.get("url") or permissoes.get("id")),
        url=_get(a, "html_url"),
    )
    return r

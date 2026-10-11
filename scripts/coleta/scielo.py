"""Cliente SciELO Brasil (ArticleMeta) — lê o JSON bruto, sem `xylose`.

Motivo da mudança (pendência 5 do documento unificado): os nomes de atributo do `xylose`
mudam entre versões e não estão documentados no repositório. O JSON do ArticleMeta é
estável e os códigos de campo estão mapeados abaixo, com a fonte de cada um.

O ArticleMeta não tem busca por termo. Estratégia:
  1. listar os periódicos SciELO da área (pela área WoS do periódico);
  2. baixar os identificadores dos artigos do periódico pedindo `publication_year` do
     recorte (pendência 6: `from`/`until` filtram data de processamento, não de
     publicação — por isso não são usados);
  3. o filtro temático pelas sementes acontece no pipeline.

É a fonte mais cara em requisições: tudo fica em cache em `data/raw/scielo`.

Códigos de campo usados (ArticleMeta/Migrate):
  periódico  v100 título, v150 título abreviado, v400 ISSN, v440 assunto,
             v441 área WoS, v450 base indexadora, v541 licença, v5/v50 situação
  artigo     v10 autores (s sobrenome, n nome), v12 título por idioma,
             v30 título abreviado do periódico, v31 volume, v32 número,
             v35 ISSN, v40 idioma original, v65 data de publicação (AAAAMMDD),
             v71 tratamento de acesso, v83 resumo por idioma, v85 palavras-chave,
             v880 identificador, v936 ano do fascículo
"""
from __future__ import annotations

import re

from comum import (get_json, ler_raw, limpar_texto, normalizar_doi, normalizar_idioma,
                   normalizar_licenca, novo_registro, salvar_raw)
from config_coleta import ANO_FIM, ANO_INICIO, AREA_WOS, MAX_ARTIGOS_POR_PERIODICO

BASE = "http://articlemeta.scielo.org/api/v1"
COLECAO = "scl"
LOTE = 100


# ------------------------------------------------------------------ utilidades
def _valores(campo):
    """Lista de dicts de um campo do ArticleMeta (sempre lista, às vezes ausente)."""
    if not campo:
        return []
    return campo if isinstance(campo, list) else [campo]


def _texto(campo, idiomas=("pt", "en")):
    """Primeiro valor textual do campo, preferindo os idiomas pedidos."""
    itens = _valores(campo)
    for idioma in idiomas:
        for item in itens:
            if item.get("l") == idioma and item.get("_"):
                return item["_"]
    for item in itens:
        if item.get("_"):
            return item["_"]
    return None


def _json(url, params):
    """GET que aceita tanto objeto quanto lista de um elemento."""
    dados = get_json(url, params)
    if isinstance(dados, list):
        return dados[0] if dados else None
    return dados


# ------------------------------------------------------------------ periódicos
def _candidatos_periodicos():
    off = 0
    while True:
        dados = get_json(f"{BASE}/journal/identifiers/",
                         {"collection": COLECAO, "limit": LOTE, "offset": off}) or {}
        objetos = dados.get("objects", [])
        if not objetos:
            return
        yield from objetos
        off += LOTE
        if off >= dados.get("meta", {}).get("total", 0):
            return


def periodicos(area):
    """Periódicos SciELO Brasil da área (cache em data/raw/scielo)."""
    nome = f"periodicos_{area}"
    cache = ler_raw("scielo", nome)
    if cache is not None:
        return cache

    lista = []
    for obj in _candidatos_periodicos():
        bruto = _json(f"{BASE}/journal/", {"collection": COLECAO, "issn": obj["code"]})
        if not bruto:
            continue
        # v854 = área WoS do periódico (equivalente a `wos_subject_areas` do xylose).
        areas = [a["_"].upper() for a in _valores(bruto.get("v854")) if a.get("_")]
        if not any(alvo in a for a in areas for alvo in AREA_WOS[area]):
            continue
        lista.append({
            "titulo": _texto(bruto.get("v100")),
            "issn": [i for i in (bruto.get("issns") or []) if i],
            "areas_wos": areas,
            "assuntos": [a["_"] for a in _valores(bruto.get("v440")) if a.get("_")],
            "indexadores": [a["_"] for a in _valores(bruto.get("v450")) if a.get("_")],
            "licenca": normalizar_licenca(_texto(bruto.get("v541"))),
        })
    salvar_raw("scielo", nome, lista)
    return lista


# ------------------------------------------------------------------ artigos
def _identificadores(issn, ano_ini=ANO_INICIO, ano_fim=ANO_FIM):
    """Identificadores dos artigos do periódico.

    `from`/`until` do ArticleMeta filtram a **data de processamento** (pendência 6 do
    documento): servem como janela barata para trazer o acervo recente, mas quem decide o
    recorte de publicação é `_ano_publicacao`, aplicado em `artigos()`.
    """
    off = 0
    while True:
        params = {
            "collection": COLECAO, "issn": issn, "limit": LOTE, "offset": off,
            "from": f"{ano_ini}-01-01", "until": f"{ano_fim}-12-31",
        }
        dados = get_json(f"{BASE}/article/identifiers/", params) or {}
        objetos = dados.get("objects", [])
        if not objetos:
            return
        yield from objetos
        off += LOTE
        if off >= dados.get("meta", {}).get("total", 0):
            return


def artigos(issn, maximo=MAX_ARTIGOS_POR_PERIODICO, ano_ini=ANO_INICIO, ano_fim=ANO_FIM):
    """Artigos brutos do periódico, mais recentes primeiro, parando ao atingir `maximo`.

    Os identificadores vêm ordenados pela data de processamento (mais antiga primeiro),
    então a lista é invertida antes de buscar. O `maximo` conta **artigos aceitos pelo
    recorte de publicação**, não identificadores lidos: periódico com acervo antigo não
    gasta requisições com artigo fora do período.
    """
    ids = list(_identificadores(issn))
    ids.sort(key=lambda o: o.get("processing_date") or "", reverse=True)

    aceitos = 0
    for obj in ids:
        pid = obj["code"]
        bruto = ler_raw("scielo", pid)
        if bruto is None:
            bruto = _json(f"{BASE}/article/",
                          {"collection": COLECAO, "code": pid, "format": "json"})
            if bruto:
                salvar_raw("scielo", pid, bruto)
        if not bruto:
            continue
        ano, _ = _ano_publicacao((bruto.get("article") or {}))
        if ano is None or not ano_ini <= ano <= ano_fim:
            continue
        yield bruto
        aceitos += 1
        if aceitos >= maximo:
            return


def _ano_publicacao(artigo):
    data = (artigo.get("v65") or [{}])[0].get("_") if artigo.get("v65") else None
    if data and re.match(r"^\d{4}", data):
        return int(data[:4]), data
    fasciculo = _valores(artigo.get("v936"))
    if fasciculo and fasciculo[0].get("y"):
        return int(fasciculo[0]["y"]), f"{fasciculo[0]['y']}0000"
    return None, None


def normalizar(bruto, licenca_periodico=None):
    """JSON bruto do ArticleMeta -> registro do esquema da base.

    A licença do artigo raramente vem no registro (`v540` costuma existir só no
    periódico); quando falta, `licenca_periodico` — lida do cadastro do periódico — é
    usada como aproximação e o campo fica registrado como vindo do periódico.
    """
    artigo = bruto.get("article") if isinstance(bruto, dict) else None
    if not artigo:
        return None
    r = novo_registro("scielo")

    ano, data = _ano_publicacao(artigo)
    idioma = _texto(artigo.get("v40"))
    palavras: dict = {}
    for item in _valores(artigo.get("v85")):
        if item.get("k"):
            palavras.setdefault(item.get("l") or idioma, []).append(item["k"])
    volume = _texto(artigo.get("v31"))
    numero = _texto(artigo.get("v32"))
    pagina_inicial = _texto(artigo.get("v702"))

    r.update(
        doi=normalizar_doi(_texto(artigo.get("v237"))),
        titulo=limpar_texto(_texto(artigo.get("v12"), (idioma or "pt", "en", "es"))),
        autores=[{"sobrenome": a.get("s") or "", "nome": a.get("n") or ""}
                 for a in _valores(artigo.get("v10")) if a.get("s")],
        ano=ano,
        _data=data,
        periodico=limpar_texto(_texto(artigo.get("v30"))),
        issn=[i["_"] for i in _valores(artigo.get("v35")) if i.get("_")],
        volume=volume,
        numero=numero,
        paginas=None,
        resumo=limpar_texto(_texto(artigo.get("v83"), (idioma or "pt", "en", "es"))),
        palavras_chave=palavras.get(idioma) or next((v for v in palavras.values() if v), []),
        idioma=normalizar_idioma(idioma),
        licenca=normalizar_licenca(_texto(artigo.get("v540"))) or licenca_periodico,
        url=None,
    )
    if pagina_inicial:
        r["paginas"] = pagina_inicial
    return r

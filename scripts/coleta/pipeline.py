"""Coleta do Marco 2: Extract -> Transform -> Load.

Uso (na raiz do repositório):  python scripts/coleta/pipeline.py
Saídas: data/knowledge_base.json, data/periodicos.json, data/relatorio_coleta.md
"""
import json
from collections import Counter, defaultdict

import crossref
import doaj
import europepmc
import medline
import scielo
from comum import CAMPOS, VAZIO, hoje, lcc_da_area, salvar_raw, sem_acento
from config_coleta import (ACEITAR_MEDLINE, ANO_FIM, ANO_INICIO, ARQ_BASE,
                           ARQ_PERIODICOS, ARQ_RELATORIO, ARTIGOS_POR_SEMENTE, DOAJ_ARTIGOS,
                           FONTES_POR_AREA, IDIOMAS, LICENCAS_ACEITAS, SEMENTES)

STOP = {"de", "da", "do", "das", "dos", "em", "no", "na", "e", "a", "o",
        "the", "of", "in", "and", "for", "on"}

# Bases declaradas pelo cadastro SciELO (`v450`) que contam como indexação válida.
BASE_INDEXADORA = {
    "doaj": "DOAJ",
    "scielo": "SciELO",
    "pubmed": "MEDLINE",
    "medline": "MEDLINE",
    "lilacs": "LILACS",
    "scopus": "Scopus",
    "web of science": "WoS",
    "latindex": "Latindex",
}


# ======================= Extract =======================================
_cache_scielo = {}
_cache_doaj = {}


def _scielo_area(area):
    """Todos os artigos SciELO da área no período (filtro temático vem depois)."""
    if area not in _cache_scielo:
        registros = []
        for p in scielo.periodicos(area):
            if not p["issn"]:
                continue
            for b in scielo.artigos(p["issn"][0]):
                reg = scielo.normalizar(b, licenca_periodico=p.get("licenca"))
                if reg:
                    registros.append(reg)
        _cache_scielo[area] = registros
    return _cache_scielo[area]


def _doaj_artigos(area):
    """Artigos do DOAJ para a área (só Computação; ver `config_coleta.DOAJ_ARTIGOS`).

    A licença vem do cadastro do periódico (`doaj.periodicos_computacao_cc`): o Article
    Search não a devolve, e sem ela o filtro do recorte descartaria todos os artigos.
    """
    consultas = DOAJ_ARTIGOS.get(area)
    if not consultas:
        return []
    if area not in _cache_doaj:
        periodicos_cc = doaj.periodicos_computacao_cc()
        registros = []
        for item in consultas:
            consulta = ('bibjson.title:"{termo}" AND bibjson.subject.term:"{assunto}" '
                        "AND bibjson.year:[{ini} TO {fim}]").format(
                termo=item["termo"], assunto=item["assunto"],
                ini=ANO_INICIO, fim=ANO_FIM)
            bruto = doaj.buscar_artigos(consulta)
            salvar_raw("doaj", f"artigos_{area}_{item['termo']}", bruto)
            for b in bruto:
                reg = doaj.normalizar_artigo(b)
                if not reg:
                    continue
                # licença e revisão vêm do cadastro do periódico
                meta = next((periodicos_cc[i] for i in reg["issn"] if i in periodicos_cc), None)
                if not meta:
                    continue
                reg["licenca"] = meta["licenca"]
                reg["_revisao"] = meta.get("revisao")
                registros.append(reg)
        _cache_doaj[area] = registros
    return _cache_doaj[area]


def extrair(area, semente):
    fontes, regs = FONTES_POR_AREA[area], []
    if "crossref" in fontes:
        for lingua in ("en", "pt"):
            itens = crossref.buscar(semente[lingua], idioma=lingua)
            salvar_raw("crossref", f"{area}_{semente['en']}_{lingua}", itens)
            regs += [crossref.normalizar(i, idioma_consulta=lingua) for i in itens]
    if "europepmc" in fontes:
        itens = europepmc.buscar(semente["en"])
        salvar_raw("europepmc", f"{area}_{semente['en']}", itens)
        regs += [europepmc.normalizar(i) for i in itens]
    if "scielo" in fontes:
        regs += [dict(r) for r in _scielo_area(area)]
    if "doaj" in fontes:
        regs += [dict(r) for r in _doaj_artigos(area)]
    # Algumas fontes devolvem palavra-chave nula dentro da lista (apareceu em Biologia);
    # sem limpar, o filtro temático quebra ao juntar o texto.
    for reg in regs:
        reg["palavras_chave"] = [p for p in reg.get("palavras_chave") or [] if p]
    return regs


# ======================= Transform =====================================
def _norm(t):
    return sem_acento((t or "").lower())


def contem_semente(reg, semente):
    """Todas as palavras da semente (pt ou en) aparecem em título/resumo/palavras-chave.
    Usa os 5 primeiros caracteres como radical simples."""
    texto = _norm(" ".join([reg["titulo"] or "", reg["resumo"] or "", " ".join(reg["palavras_chave"])]))
    for termo in semente.values():
        palavras = [p for p in _norm(termo).split() if p not in STOP]
        if all(p[:5] in texto for p in palavras):
            return True
    return False


def filtro_basico(reg):
    """Motivo de descarte, ou None. Reaplicado após o enriquecimento Crossref."""
    if not reg["doi"]:
        return "sem_doi"
    if not reg["ano"] or not ANO_INICIO <= reg["ano"] <= ANO_FIM:
        return "fora_do_periodo"
    if reg["idioma"] not in IDIOMAS:
        return "idioma"
    if reg["licenca"] not in LICENCAS_ACEITAS:
        return "licenca"
    return None


def mesclar(destino, outro):
    """Preenche campos vazios de destino com os de outro (duplicata entre fontes)."""
    for campo, valor in outro.items():
        if destino.get(campo) in VAZIO and valor not in VAZIO:
            destino[campo] = valor


def enriquecer(reg):
    """Valida o DOI e aplica a regra: Crossref prevalece em conflito; campo vazio no Crossref mantém o da origem."""
    item = crossref.por_doi(reg["doi"])
    if not item:
        return False
    for campo, valor in crossref.normalizar(item).items():
        if campo != "fonte" and valor not in VAZIO:
            reg[campo] = valor
    return True


def indexacao(reg, scielo_por_issn):
    dados_doaj = next((d for d in map(doaj.periodico_por_issn, reg["issn"]) if d), None)
    ind = []
    if dados_doaj:
        ind.append("DOAJ")
    if any(i in scielo_por_issn for i in reg["issn"]):
        ind.append("SciELO")
    if ACEITAR_MEDLINE and any(map(medline.indexado, reg["issn"])):
        ind.append("MEDLINE")
    # O cadastro SciELO declara as bases em que o periódico está indexado (`v450`).
    scielo_meta = next((scielo_por_issn[i] for i in reg["issn"] if i in scielo_por_issn), None)
    for base in (scielo_meta or {}).get("indexadores", []):
        normalizada = BASE_INDEXADORA.get(base.strip().lower())
        if normalizada and normalizada not in ind:
            ind.append(normalizada)
    return ind, dados_doaj


def area_confere(area, reg, dados_doaj, scielo_por_issn):
    """True/False pela LCC (DOAJ) ou área WoS (SciELO); None se não há assunto (ex.: só MEDLINE)."""
    if dados_doaj and dados_doaj["lcc"]:
        return lcc_da_area(area, dados_doaj["lcc"])
    sc = next((scielo_por_issn[i] for i in reg["issn"] if i in scielo_por_issn), None)
    return area in sc["areas"] if sc else None


def recuperar_interno(reg):
    """Devolve o campo interno `_data` de um registro que veio do JSON já gravado.

    O Load descarta os campos internos de propósito, mas `ordenar` e a mescla precisam
    deles. Sem isso, um registro reaproveitado da base perde a posição na ordenação por
    data e vai para o fim da lista.
    """
    reg = dict(reg)
    if not reg.get("_data"):
        ano = reg.get("ano")
        reg["_data"] = f"{ano}-01-01" if ano else None
    return reg


def ordenar(regs):
    """Mais recente primeiro; desempate por DOI.

    Usa `.get('_data')` porque registros vindos do JSON já gravado não têm os campos
    internos (ele é descartado no Load).
    """
    return sorted(sorted(regs, key=lambda r: r.get("doi") or ""),
                  key=lambda r: r.get("_data") or "", reverse=True)


def intercalar_anos(regs):
    """Ordem de validação que espalha a cota pelos anos do recorte.

    Pega o mais recente de cada ano, do ano mais novo ao mais antigo, e repete. Validar só
    do mais recente para trás enchia a cota com os dois últimos anos e deixava a janela de
    10 anos só no papel.
    """
    por_ano = defaultdict(list)
    for reg in ordenar(regs):
        por_ano[reg.get("ano")].append(reg)
    filas = [por_ano[a] for a in sorted(por_ano, key=lambda a: a or 0, reverse=True)]
    saida = []
    for i in range(max(map(len, filas), default=0)):
        saida += [fila[i] for fila in filas if i < len(fila)]
    return saida


def registrar_periodico(periodicos, reg, ind, dados_doaj):
    """Registra/atualiza o periódico na lista curada.

    Guarda `indexacao`, `revisao` e `licenca` porque são exatamente os três critérios que a
    intenção `avaliar_fonte` usa para dar o parecer (seção 4 do documento).
    """
    chave = reg["issn"][0] if reg["issn"] else reg["periodico"]
    p = periodicos.setdefault(chave, {
        "titulo": (dados_doaj or {}).get("titulo") or reg["periodico"],
        "issn": reg["issn"], "indexacao": [],
        "assuntos": (dados_doaj or {}).get("assuntos", []),
        "revisao": (dados_doaj or {}).get("revisao", []),
        "licenca": reg.get("licenca"),
        "url": (dados_doaj or {}).get("url") or reg.get("url"),
    })
    p["indexacao"] = sorted(set(p["indexacao"]) | set(ind))
    p["licenca"] = p.get("licenca") or reg.get("licenca")


def selecionar_area(area, vistos, funil, scielo_por_issn, periodicos):
    escolhidos, sobra = [], 0
    for semente in SEMENTES[area]:
        cota = ARTIGOS_POR_SEMENTE + sobra   # semente curta passa a sobra para a próxima
        f = funil[f"{area} | {semente['pt']}"]

        candidatos = {}
        for reg in extrair(area, semente):
            f["extraidos"] += 1
            motivo = filtro_basico(reg) or (None if contem_semente(reg, semente) else "fora_do_tema")
            if motivo:
                f[motivo] += 1
            elif reg["doi"] in vistos:
                f["ja_em_outra_semente"] += 1
            elif reg["doi"] in candidatos:
                mesclar(candidatos[reg["doi"]], reg)
                f["duplicado_entre_fontes"] += 1
            else:
                candidatos[reg["doi"]] = reg

        aceitos = []
        for reg in intercalar_anos(candidatos.values()):   # valida só até preencher a cota
            if len(aceitos) >= cota:
                break
            if not enriquecer(reg):
                f["doi_inexistente"] += 1
                continue
            motivo = filtro_basico(reg)
            if motivo:
                f[f"{motivo}_pos_crossref"] += 1
                continue
            ind, dados_doaj = indexacao(reg, scielo_por_issn)
            if not ind:
                f["periodico_nao_indexado"] += 1
                continue
            confere = area_confere(area, reg, dados_doaj, scielo_por_issn)
            if confere is False:
                f["area_divergente"] += 1
                continue
            if confere is None:
                f["area_nao_conferida"] += 1   # aceito, mas registrado no relatório
            reg["area"] = area
            aceitos.append(reg)
            vistos.add(reg["doi"])
            registrar_periodico(periodicos, reg, ind, dados_doaj)

        f["selecionados"] = len(aceitos)
        sobra = cota - len(aceitos)
        escolhidos += aceitos
    if sobra:
        funil[f"{area} | TOTAL"]["faltaram"] = sobra
    return ordenar(escolhidos)


# ======================= Load ==========================================
def relatorio(base, funil):
    """Relatório de coleta (Marco 2): volume, recorte, licenças e o funil de descartes.

    As pendências 2 e 3 do documento unificado pedem que a licença de cada fonte fique
    registrada; por isso o relatório traz a licença por fonte e por área.
    """
    linhas = [f"# Relatório de coleta — {hoje()}", "",
              f"Período {ANO_INICIO}–{ANO_FIM} · idiomas {sorted(IDIOMAS)} · "
              f"licenças {sorted(LICENCAS_ACEITAS)} · MEDLINE aceito: {ACEITAR_MEDLINE}", "",
              f"Total: {len(base)} artigos", ""]
    for rotulo, campo in (("Área", "area"), ("Idioma", "idioma"), ("Fonte", "fonte"),
                          ("Licença", "licenca")):
        contagem = Counter(a.get(campo) for a in base)
        linhas.append(f"**{rotulo}:** " + ", ".join(f"{k} {v}" for k, v in contagem.items()))

    linhas += ["", "## Licença por fonte", "",
               "Cada fonte de metadados só entra com licença registrada como CC-BY ou CC0 "
               "(risco 'licença de resumos impede redistribuição').", ""]
    for fonte in sorted({a.get("fonte") for a in base}):
        contagem = Counter(a.get("licenca") for a in base if a.get("fonte") == fonte)
        linhas.append(f"- **{fonte}**: " + ", ".join(f"{k} {v}" for k, v in contagem.items()))

    sem_resumo = sum(1 for a in base if not a.get("resumo"))
    sem_doi = sum(1 for a in base if not a.get("doi"))
    linhas += ["", "## Qualidade dos registros", "",
               f"- Artigos sem resumo (ficam só com título e palavras-chave): {sem_resumo}",
               f"- Artigos sem DOI (não deveriam existir; a validação exige DOI): {sem_doi}",
               f"- Periódicos distintos: {len({i for a in base for i in (a.get('issn') or [])})}", ""]

    linhas += ["## Funil por semente", ""]
    for chave, contagem in funil.items():
        linhas.append(f"- **{chave}**: " + ", ".join(f"{k} {v}" for k, v in contagem.items()))

    linhas += ["", "## Observações de curadoria", "",
               "- O filtro de período usa a **data de publicação** do artigo (`v65` no "
               "ArticleMeta), não a data de processamento.",
               "- A licença do artigo do SciELO costuma existir só no cadastro do "
               "periódico; nesse caso a licença do periódico é registrada e conferida no DOAJ.",
               "- A conferência de área usa a LCC do DOAJ e, quando falta, a área WoS do "
               "cadastro SciELO; artigos sem nenhuma das duas são aceitos e contados como "
               "`area_nao_conferida` no funil.",
               "- A validação de cada semente intercala os anos (o mais recente de cada ano, "
               "do ano mais novo ao mais antigo), para a cota cobrir a janela inteira.",
               ""]
    return "\n".join(linhas)


def carregar(artigos, periodicos, funil, arquivos=None):
    """Grava as três saídas do Load. `arquivos` permite redirecionar para teste."""
    arq_base, arq_periodicos, arq_relatorio = arquivos or (ARQ_BASE, ARQ_PERIODICOS, ARQ_RELATORIO)
    data, base = hoje(), []
    for n, reg in enumerate(artigos, 1):
        reg.update(id=f"art_{n:03d}", data_coleta=data)
        base.append({c: reg.get(c) for c in CAMPOS})   # descarta campos internos (_data)
    arq_base.write_text(json.dumps(base, ensure_ascii=False, indent=2), encoding="utf-8")
    arq_periodicos.write_text(json.dumps(list(periodicos.values()), ensure_ascii=False, indent=2),
                              encoding="utf-8")
    arq_relatorio.write_text(relatorio(base, funil), encoding="utf-8")
    print(f"{len(base)} artigos e {len(periodicos)} periódicos gravados.")


def base_da_area(regs, areas):
    """Separa a base gravada em (registros de outras áreas, registros por área alvo).

    A área que vai rodar sai do merge e é recolhida do zero — se ficasse em `vistos`, os
    próprios DOIs dela bloqueariam a recoleta.
    """
    outras = [r for r in regs if r.get("area") not in areas]
    anteriores = {area: [r for r in regs if r.get("area") == area] for area in areas}
    return outras, anteriores


def main(areas=None, arquivos=None, coletar=None):
    """Roda o ETL. Sem `areas`, faz as cinco do recorte.

    `python scripts/coleta/pipeline.py --area odontologia` roda uma área por vez; as
    saídas das áreas já rodadas são preservadas (merge por DOI), porque a coleta completa
    pode levar bastante tempo e não deve ser perdida no meio.

    Re-rodar uma área **recoleta** essa área e substitui o que estava na base. Se a
    recoleta não trouxer nada, a versão anterior é mantida: sem essa guarda, uma rodada
    que falha (API fora do ar, filtro mudado) apaga a área silenciosamente.

    `arquivos` e `coletar` existem para o teste do merge
    (`tests/test_pipeline_coleta.py`) rodar sem rede e sem tocar em `data/`.
    """
    areas = areas or list(SEMENTES)
    desconhecidas = [a for a in areas if a not in SEMENTES]
    if desconhecidas:
        raise SystemExit(f"área desconhecida: {', '.join(desconhecidas)}. "
                         f"Use: {', '.join(SEMENTES)}")

    arq_base, arq_periodicos, arq_relatorio = arquivos or (ARQ_BASE, ARQ_PERIODICOS, ARQ_RELATORIO)
    # `scielo.periodicos` faz rede; quem injeta uma coleta falsa (`coletar`) não precisa
    # dessa lista, e pulá-la deixa o teste do merge sem tocar a internet. O teste tem de
    # vir ANTES do padrão de `coletar`: na ordem inversa o índice ficava sempre vazio e a
    # indexação SciELO e a área WoS nunca eram conferidas numa coleta real.
    # Um periódico pode estar em mais de uma área (Psiquiatria e Psicologia, por exemplo).
    scielo_por_issn = {}
    if coletar is None:
        for area in areas:
            for p in scielo.periodicos(area):
                for i in p["issn"]:
                    scielo_por_issn.setdefault(i, {**p, "areas": set()})["areas"].add(area)
    coletar = coletar or selecionar_area
    vistos, periodicos, funil = set(), {}, defaultdict(Counter)

    # Estado inicial: o que já está gravado entra no merge; a área que vai rodar sai e é
    # recolhida do zero.
    artigos: list[dict] = []
    anteriores: dict[str, list[dict]] = {}
    if arq_base.exists():
        base = json.loads(arq_base.read_text(encoding="utf-8"))
        artigos, anteriores = base_da_area(base, areas)
        vistos = {a["doi"] for a in artigos if a.get("doi")}
    if arq_periodicos.exists():
        for p in json.loads(arq_periodicos.read_text(encoding="utf-8")):
            chave = (p.get("issn") or [p.get("titulo")])[0]
            periodicos[chave] = p

    for area in areas:
        novos = coletar(area, vistos, funil, scielo_por_issn, periodicos)
        antigos = anteriores.get(area) or []
        if not novos and antigos:
            print(f"AVISO: a recoleta de {area} não trouxe nenhum artigo; "
                  f"mantendo os {len(antigos)} artigos que já estavam na base.")
            # devolve os DOIs dos antigos, senão a mescla de outra área os veria como vistos
            vistos -= {a["doi"] for a in antigos if a.get("doi")}
            novos = [recuperar_interno(a) for a in antigos]
        artigos += novos
    carregar(ordenar(artigos), periodicos, funil, (arq_base, arq_periodicos, arq_relatorio))


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Coleta do Artikel (Marco 2)")
    ap.add_argument("--area", action="append", choices=list(SEMENTES),
                    help="roda só esta área (pode repetir); padrão: todas")
    main(ap.parse_args().area)
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
from comum import CAMPOS, VAZIO, hoje, salvar_raw, sem_acento
from config_coleta import (ACEITAR_MEDLINE, ANO_FIM, ANO_INICIO, AREA_LCC, ARQ_BASE,
                           ARQ_PERIODICOS, ARQ_RELATORIO, ARTIGOS_POR_SEMENTE,
                           FONTES_POR_AREA, IDIOMAS, LICENCAS_ACEITAS, SEMENTES)

STOP = {"de", "da", "do", "das", "dos", "em", "no", "na", "e", "a", "o",
        "the", "of", "in", "and", "for", "on"}


# ======================= Extract =======================================
_cache_scielo = {}


def _scielo_area(area):
    """Todos os artigos SciELO da área no período (filtro temático vem depois)."""
    if area not in _cache_scielo:
        _cache_scielo[area] = [scielo.normalizar(b)
                               for p in scielo.periodicos(area) if p["issn"]
                               for b in scielo.artigos(p["issn"][0])]
    return _cache_scielo[area]


def extrair(area, semente):
    fontes, regs = FONTES_POR_AREA[area], []
    if "crossref" in fontes:
        for lingua in ("en", "pt"):
            itens = crossref.buscar(semente[lingua])
            salvar_raw("crossref", f"{area}_{semente['en']}_{lingua}", itens)
            regs += [crossref.normalizar(i) for i in itens]
    if "europepmc" in fontes:
        itens = europepmc.buscar(semente["en"])
        salvar_raw("europepmc", f"{area}_{semente['en']}", itens)
        regs += [europepmc.normalizar(i) for i in itens]
    if "scielo" in fontes:
        regs += [dict(r) for r in _scielo_area(area)]
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
    return ind, dados_doaj


def area_confere(area, reg, dados_doaj, scielo_por_issn):
    """True/False pela LCC (DOAJ) ou área WoS (SciELO); None se não há assunto (ex.: só MEDLINE)."""
    if dados_doaj and dados_doaj["lcc"]:
        return any(c.startswith(p) for c in dados_doaj["lcc"] for p in AREA_LCC[area])
    sc = next((scielo_por_issn[i] for i in reg["issn"] if i in scielo_por_issn), None)
    return sc["area"] == area if sc else None


def ordenar(regs):
    """Mais recente primeiro; desempate por DOI."""
    return sorted(sorted(regs, key=lambda r: r["doi"]),
                  key=lambda r: r["_data"] or "", reverse=True)


def registrar_periodico(periodicos, reg, ind, dados_doaj):
    chave = reg["issn"][0] if reg["issn"] else reg["periodico"]
    p = periodicos.setdefault(chave, {
        "titulo": (dados_doaj or {}).get("titulo") or reg["periodico"],
        "issn": reg["issn"], "indexacao": [],
        "assuntos": (dados_doaj or {}).get("assuntos", []),
        "revisao": (dados_doaj or {}).get("revisao", []),
        "url": (dados_doaj or {}).get("url"),
    })
    p["indexacao"] = sorted(set(p["indexacao"]) | set(ind))


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
        for reg in ordenar(candidatos.values()):   # valida só até preencher a cota
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
    linhas = [f"# Relatório de coleta — {hoje()}", "",
              f"Período {ANO_INICIO}–{ANO_FIM} · idiomas {sorted(IDIOMAS)} · "
              f"licenças {sorted(LICENCAS_ACEITAS)} · MEDLINE aceito: {ACEITAR_MEDLINE}", "",
              f"Total: {len(base)} artigos", ""]
    for rotulo, campo in (("Área", "area"), ("Idioma", "idioma"), ("Fonte", "fonte")):
        linhas.append(f"**{rotulo}:** " + ", ".join(f"{k} {v}" for k, v in Counter(a[campo] for a in base).items()))
    linhas += ["", "## Funil por semente", ""]
    for chave, contagem in funil.items():
        linhas.append(f"- **{chave}**: " + ", ".join(f"{k} {v}" for k, v in contagem.items()))
    return "\n".join(linhas) + "\n"


def carregar(artigos, periodicos, funil):
    data, base = hoje(), []
    for n, reg in enumerate(artigos, 1):
        reg.update(id=f"art_{n:03d}", data_coleta=data)
        base.append({c: reg.get(c) for c in CAMPOS})   # descarta campos internos (_data)
    ARQ_BASE.write_text(json.dumps(base, ensure_ascii=False, indent=2), encoding="utf-8")
    ARQ_PERIODICOS.write_text(json.dumps(list(periodicos.values()), ensure_ascii=False, indent=2),
                              encoding="utf-8")
    ARQ_RELATORIO.write_text(relatorio(base, funil), encoding="utf-8")
    print(f"{len(base)} artigos e {len(periodicos)} periódicos gravados.")


def main():
    scielo_por_issn = {i: {**p, "area": area}
                       for area in SEMENTES for p in scielo.periodicos(area) for i in p["issn"]}
    vistos, periodicos, funil = set(), {}, defaultdict(Counter)
    artigos = []
    for area in SEMENTES:
        artigos += selecionar_area(area, vistos, funil, scielo_por_issn, periodicos)
    carregar(artigos, periodicos, funil)


if __name__ == "__main__":
    main()
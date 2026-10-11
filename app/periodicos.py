"""Parecer sobre periódico/fonte pela lista curada (intenção `avaliar_fonte`).

Regra do documento: **fora da lista curada -> "não consta na base"**. O bot nunca afirma
que uma fonte é confiável por conta própria; ele relata indexação, revisão por pares e
licença registradas na curadoria.
"""
from __future__ import annotations

import re

from recuperacao import Motor, sem_acento

# Fontes que aparecem nas perguntas simuladas e não são periódicos: o parecer é sobre o
# tipo de fonte, não sobre indexação.
FONTES_GENERICAS = {
    "wikipedia": (
        "A Wikipédia não passa por revisão por pares e qualquer pessoa pode editar, então "
        "ela não serve como referência principal no TCC. Use-a só para localizar a "
        "bibliografia indicada no fim do verbete e vá ao artigo original."
    ),
    "blog": (
        "Blog e site de conteúdo não têm revisão por pares nem indexação acadêmica. "
        "Servem para contexto, não como referência principal: substitua por um artigo "
        "revisado sobre o mesmo assunto."
    ),
    "site do governo": (
        "Documento oficial de órgão público é fonte primária e pode ser citado como tal, "
        "mas não substitui a literatura revisada por pares no referencial teórico."
    ),
    "google academico": (
        "O Google Acadêmico é um buscador, não uma fonte: ele mistura artigo revisado, "
        "tese, slide e preprint. Descubra o título por ele e cite a página do periódico."
    ),
    "doaj": (
        "O DOAJ (Directory of Open Access Journals) é a lista de referência de periódicos "
        "de acesso aberto: para entrar, o periódico precisa declarar revisão por pares e "
        "política de licença. Estar no DOAJ é um bom sinal, mas o Artikel só considera "
        "verificado quando o periódico também está na lista curada."
    ),
    "acesso aberto": (
        "Acesso aberto quer dizer que o texto é livre para ler, não que a revista seja "
        "confiável: existem periódicos predatórios que também cobram para publicar em "
        "acesso aberto. Confirme a indexação no DOAJ, no SciELO ou no MEDLINE."
    ),
}

_ISSN = re.compile(r"\b(\d{4}-\d{3}[\dxX])\b")


def avaliar(pergunta: str, motor: Motor) -> dict:
    """Devolve o parecer estruturado. `encontrado=False` -> não consta na base."""
    # Sem acento para casar "Wikipédia" com a chave "wikipedia".
    texto = sem_acento(pergunta).lower()
    for chave, explicacao in FONTES_GENERICAS.items():
        if chave in texto:
            return {
                "encontrado": True,
                "tipo": "generica",
                "fonte": chave,
                "titulo": chave.title(),
                "indexacao": [],
                "revisao": [],
                "licenca": None,
                "url": None,
                "explicacao": explicacao,
            }

    issns = _ISSN.findall(pergunta)
    achados = []
    for issn in issns:
        achados += motor.buscar_periodico(issn)
    achados += motor.buscar_periodico(pergunta)
    # remove repetidos preservando a ordem
    vistos, periodicos = set(), []
    for p in achados:
        chave = tuple(p.get("issn") or [p.get("titulo")])
        if chave not in vistos:
            vistos.add(chave)
            periodicos.append(p)

    if not periodicos:
        return {
            "encontrado": False,
            "tipo": "desconhecida",
            "fonte": None,
            "explicacao": (
                "Não consta na base curada do Artikel. Isso não quer dizer que a fonte "
                "seja ruim: quer dizer que a equipe ainda não registrou indexação e "
                "revisão por pares dela. Para citar, confirme no DOAJ, no SciELO ou no "
                "MEDLINE e leve a dúvida ao orientador."
            ),
        }

    p = periodicos[0]
    ind = p.get("indexacao") or []
    revisao = p.get("revisao") or []
    if ind:
        explicacao = (
            "Consta na base curada com indexação em "
            + ", ".join(sorted(set(ind)))
            + ". Indexação em base reconhecida é o critério que o Artikel usa para "
            "recomendar um periódico."
        )
    else:
        explicacao = (
            "Consta na base curada, mas sem indexação registrada em DOAJ, SciELO ou "
            "MEDLINE: trate como não verificado."
        )
    if revisao:
        explicacao += " Revisão declarada: " + ", ".join(revisao) + "."
    else:
        explicacao += " A política de revisão por pares não está registrada na curadoria."

    return {
        "encontrado": True,
        "tipo": "periodico",
        "fonte": p.get("titulo"),
        "titulo": p.get("titulo"),
        "issns": p.get("issn") or [],
        "indexacao": sorted(set(ind)),
        "revisao": revisao,
        "licenca": p.get("licenca"),
        "url": p.get("url"),
        "explicacao": explicacao,
    }

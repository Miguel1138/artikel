"""Avaliação do Artikel (R6, Marco 5).

Roda `tests/casos_teste.csv` de ponta a ponta e calcula as quatro métricas do documento:

    acurácia de intenções      (meta >= 85%)  — com matriz de confusão
    Precisão@5 da recuperação  (meta >= 0,6)  — relevância julgada por `tema_esperado`
    abstenção correta fora de escopo (meta >= 90%)
    citações inventadas        (meta = 0)     — todo DOI exibido existe na base

Uso:
    python tests/avaliar.py                 # relatório em texto
    python tests/avaliar.py --json rel.json # também grava os resultados brutos
    python tests/avaliar.py --md docs/avaliacao.md
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "app"))

import fluxo  # noqa: E402
import recuperacao  # noqa: E402
from config import ARQ_CASOS, INTENCOES, K_PRECISAO  # noqa: E402
from preprocessamento import sem_acento, termos_relevantes  # noqa: E402

# Casos ambíguos: o documento aceita mais de um desfecho (ex.: abstenção é resposta
# correta para "me escreve o referencial teórico"). Ver `melhor_desfecho`.
ABSTENCAO_ACEITA = {"16"}


def ler_casos(caminho: Path = ARQ_CASOS) -> list[dict]:
    with caminho.open(encoding="utf-8", newline="") as fh:
        return [l for l in csv.DictReader(fh) if (l.get("pergunta") or "").strip()]


def _termo_presente(termo: str, texto: str) -> bool:
    """Casa o tema esperado por radical: 'aprendizado de maquina' acha 'machine learning'?"""
    alvo = sem_acento(texto).lower()
    for palavra in termos_relevantes(termo):
        if len(palavra) >= 4 and palavra[:5] in alvo:
            return True
    return False


def precisao_at_k(artigos: list[dict], tema: str, k: int = K_PRECISAO) -> float:
    """Fração dos k primeiros artigos cujo tema casa com o esperado.

    A Precisão@5 do documento é sobre a lista **exibida**: se o fluxo se absteve (ou
    devolveu menos que k), o denominador é o que foi exibido, não 5. Contar 5 sempre
    transformaria "abster quando não há registro" — comportamento correto e exigido — em
    penalidade de precisão.
    """
    if not tema:
        return 1.0
    if not artigos:
        return 0.0
    relevantes = sum(
        1 for a in artigos[:k]
        if _termo_presente(tema, " ".join([
            a.get("titulo") or "",
            a.get("resumo") or "",
            " ".join(a.get("palavras_chave") or []),
        ]))
    )
    return relevantes / min(k, len(artigos))


def avaliar(casos: list[dict]) -> dict:
    motor = recuperacao.obter()
    if not motor.pronto:
        raise SystemExit(
            "A base curada não está disponível. Rode antes: python scripts/coleta/pipeline.py"
        )

    ids_base = {a.get("id") for a in motor.artigos}
    dois_base = {a.get("doi") for a in motor.artigos if a.get("doi")}

    registros, acertos = [], 0
    confusao = Counter()
    precisoes: list[float] = []
    fora_escopo_total = fora_escopo_abstido = 0
    citacoes_inventadas = 0
    ultimo_resultado = None

    for linha in casos:
        pergunta = linha["pergunta"]
        esperado = (linha.get("intencao_esperada") or "").strip()
        tipo = (linha.get("tipo") or "").strip()
        tema = (linha.get("tema_esperado") or "").strip()
        case_id = (linha.get("id") or "").strip()

        # As linhas de contexto (18 e 19) só fazem sentido depois de uma busca.
        if tipo == "contexto" and ultimo_resultado is not None:
            pergunta_efetiva = f"{ultimo_resultado['pergunta_base']} e {pergunta}"
        else:
            pergunta_efetiva = pergunta

        r = fluxo.responder(pergunta, sessao=f"avaliacao_{case_id}")
        previsto = r.intencao
        confusao[(esperado, previsto)] += 1

        aceito = previsto == esperado
        if case_id in ABSTENCAO_ACEITA and r.tipo == "abstencao":
            aceito = True  # abstenção é resposta correta na ambiguidade declarada
        if tipo == "contexto" and r.tipo == "referencia_abnt":
            aceito = previsto == esperado
        acertos += int(aceito)

        artigos_brutos = [
            motor.por_id(a.id) or {} for a in r.artigos
        ]
        if esperado == "buscar_referencias" and previsto == "buscar_referencias":
            precisoes.append(precisao_at_k(artigos_brutos, tema))

        if esperado == "fora_de_escopo":
            fora_escopo_total += 1
            fora_escopo_abstido += int(r.tipo == "abstencao")

        for a in r.artigos:
            if a.id not in ids_base:
                citacoes_inventadas += 1
            if a.doi and a.doi not in dois_base:
                citacoes_inventadas += 1

        if previsto == "buscar_referencias" and r.artigos:
            ultimo_resultado = {
                "pergunta_base": pergunta,
                "ids": [a.id for a in r.artigos],
            }

        registros.append({
            "id": case_id,
            "pergunta": pergunta,
            "esperado": esperado,
            "previsto": previsto,
            "tipo": tipo,
            "confianca": r.traco.confianca,
            "tipo_resposta": r.tipo,
            "acao": r.traco.acao,
            "regra": r.traco.regra,
            "n_artigos": len(r.artigos),
            "score_maximo": r.traco.score_maximo,
            "aceito": bool(aceito),
        })

    total = len(registros)
    return {
        "total_casos": total,
        "acuracia": acertos / total if total else 0.0,
        "precisao_at_5": sum(precisoes) / len(precisoes) if precisoes else 0.0,
        "casos_com_busca": len(precisoes),
        "abstencao_fora_de_escopo": (fora_escopo_abstido / fora_escopo_total)
        if fora_escopo_total else 0.0,
        "fora_de_escopo_total": fora_escopo_total,
        "citacoes_inventadas": citacoes_inventadas,
        "matriz_confusao": {
            e: {p: confusao.get((e, p), 0) for p in INTENCOES} for e in INTENCOES
        },
        "registros": registros,
    }


def relatorio_texto(res: dict) -> str:
    linhas = ["=" * 68, "AVALIAÇÃO DO ARTIKEL — casos_teste.csv", "=" * 68, ""]
    metas = [
        ("Acurácia de intenções", res["acuracia"], 0.85),
        ("Precisão@5 da recuperação", res["precisao_at_5"], 0.60),
        ("Abstenção correta fora de escopo", res["abstencao_fora_de_escopo"], 0.90),
    ]
    linhas.append(f"{'Métrica':34} {'Valor':>8}  {'Meta':>6}  Situação")
    for nome, valor, meta in metas:
        situacao = "OK" if valor >= meta else "ABAIXO"
        linhas.append(f"{nome:34} {valor:8.3f}  {meta:6.2f}  {situacao}")
    inv = res["citacoes_inventadas"]
    linhas.append(f"{'Citações inventadas':34} {inv:8d}  {0:6d}  "
                  f"{'OK' if inv == 0 else 'ABAIXO'}")
    linhas += ["", f"Casos: {res['total_casos']} | com busca avaliada: {res['casos_com_busca']}", ""]

    linhas.append("Matriz de confusão (linha = esperado, coluna = previsto)")
    abreviado = {i: i[:9] for i in INTENCOES}
    linhas.append(" " * 22 + " ".join(f"{abreviado[i]:>9}" for i in INTENCOES))
    for esperado in INTENCOES:
        linha = res["matriz_confusao"][esperado]
        linhas.append(f"{esperado:20}  " + " ".join(f"{linha[p]:>9}" for p in INTENCOES))
    linhas.append("")

    erros = [r for r in res["registros"] if not r["aceito"]]
    linhas.append(f"Erros e abstenções ({len(erros)}):")
    for r in erros:
        linhas.append(
            f"  [{r['id']:>2}] esperado={r['esperado']:<20} previsto={r['previsto']:<20} "
            f"conf={r['confianca']:.2f} resposta={r['tipo_resposta']:<18} | {r['pergunta'][:52]}"
        )
    linhas.append("")
    linhas.append("Detalhe por caso:")
    for r in res["registros"]:
        marca = "ok " if r["aceito"] else "XX "
        linhas.append(
            f"  {marca}[{r['id']:>2}] {r['previsto']:<20} acao={r['acao']:<11} "
            f"artigos={r['n_artigos']} score={r['score_maximo']} | {r['pergunta'][:46]}"
        )
    return "\n".join(linhas) + "\n"


def relatorio_md(res: dict) -> str:
    """Versão para o relatório do Marco 6."""
    l = ["# Avaliação — Artikel", "",
         f"Casos em `tests/casos_teste.csv`: **{res['total_casos']}** "
         f"(marco 5 do cronograma).", "",
         "## Métricas", "",
         "| Métrica | Resultado | Meta | Situação |", "|---|---|---|---|"]
    for nome, valor, meta in [
        ("Acurácia de intenções", res["acuracia"], 0.85),
        ("Precisão@5 da recuperação", res["precisao_at_5"], 0.60),
        ("Abstenção correta fora de escopo", res["abstencao_fora_de_escopo"], 0.90),
    ]:
        l.append(f"| {nome} | {valor:.3f} | {meta:.2f} | {'OK' if valor >= meta else 'abaixo'} |")
    l.append(f"| Citações inventadas | {res['citacoes_inventadas']} | 0 | "
             f"{'OK' if res['citacoes_inventadas'] == 0 else 'abaixo'} |")
    l += ["", "## Matriz de confusão", "",
          "| esperado \\ previsto | " + " | ".join(INTENCOES) + " |",
          "|---" * (len(INTENCOES) + 1) + "|"]
    for e in INTENCOES:
        linha = res["matriz_confusao"][e]
        l.append(f"| {e} | " + " | ".join(str(linha[p]) for p in INTENCOES) + " |")
    l += ["", "## Casos que não passaram", ""]
    erros = [r for r in res["registros"] if not r["aceito"]]
    if not erros:
        l.append("Nenhum.")
    else:
        l += ["| id | pergunta | esperado | previsto | confiança | resposta |",
              "|---|---|---|---|---|---|"]
        for r in erros:
            l.append(f"| {r['id']} | {r['pergunta']} | {r['esperado']} | {r['previsto']} "
                     f"| {r['confianca']:.2f} | {r['tipo_resposta']} |")
    return "\n".join(l) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description="Avaliação do Artikel")
    ap.add_argument("--json", help="grava os resultados brutos em JSON")
    ap.add_argument("--md", help="grava o relatório em Markdown")
    args = ap.parse_args()

    res = avaliar(ler_casos())
    print(relatorio_texto(res))
    if args.json:
        Path(args.json).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"JSON gravado em {args.json}")
    if args.md:
        Path(args.md).write_text(relatorio_md(res), encoding="utf-8")
        print(f"Markdown gravado em {args.md}")


if __name__ == "__main__":
    main()

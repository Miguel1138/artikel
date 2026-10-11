"""Repete a avaliação várias vezes para detectar resultado não determinístico.

Uso: python scripts/diagnostico/_diag_determinismo.py [n]

Se duas rodadas com a mesma base e o mesmo modelo derem números diferentes, há ordem
implícita (conjunto, dicionário ou desempate) em algum ponto da recuperação — e o número
que vai para o relatório deixa de ser confiável.
"""
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def rodada() -> dict:
    saida = subprocess.run(
        [sys.executable, str(RAIZ / "tests" / "avaliar.py"), "--json",
         str(RAIZ / "tests" / "_temporario" / "determinismo.json")],
        capture_output=True, text=True, encoding="utf-8", cwd=RAIZ,
    )
    if saida.returncode not in (0, 1):
        raise SystemExit("avaliar.py falhou:\n" + saida.stderr[-2000:])
    return json.loads((RAIZ / "tests" / "_temporario" / "determinismo.json").read_text(encoding="utf-8"))


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    (RAIZ / "tests" / "_temporario").mkdir(parents=True, exist_ok=True)

    metricas = Counter()
    por_caso = Counter()
    for i in range(n):
        res = rodada()
        metricas[round(res["precisao_at_5"], 4)] += 1
        for r in res["registros"]:
            por_caso[(r["id"], r["previsto"], r["tipo_resposta"], r["n_artigos"])] += 1
        print(f"rodada {i + 1}: acurácia {res['acuracia']:.3f} | "
              f"Precisão@5 {res['precisao_at_5']:.4f} | abstenção {res['abstencao_fora_de_escopo']:.3f}")

    print(f"\nPrecisão@5 por rodada: {dict(metricas)}")
    if len(metricas) > 1:
        print("NAO DETERMINISTICO: a mesma base e o mesmo modelo deram resultados diferentes.")
    else:
        print("determinístico nas", n, "rodadas")

    variacoes = {k: v for k, v in por_caso.items() if v != n}
    if variacoes:
        print("\nCasos que variaram entre rodadas:")
        for (case_id, previsto, tipo, n_artigos), vezes in sorted(variacoes.items()):
            print(f"  caso {case_id}: {vezes}/{n} rodadas com previsto={previsto} "
                  f"resposta={tipo} artigos={n_artigos}")


if __name__ == "__main__":
    main()

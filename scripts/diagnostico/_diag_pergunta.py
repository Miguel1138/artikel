"""Investiga uma pergunta concreta: intenção, área, candidatos e cobertura.

Uso:
    python scripts/diagnostico/_diag_pergunta.py "computação quântica"
    python scripts/diagnostico/_diag_pergunta.py "computação quântica" --sem-guarda
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "app"))

import intencoes  # noqa: E402
import recuperacao  # noqa: E402
from config import COBERTURA_MINIMA, LIMIAR_CONFIANCA, LIMIAR_SCORE  # noqa: E402


def investigar(pergunta: str, sem_guarda: bool = False) -> None:
    motor = recuperacao.Motor()
    print(f"pergunta: {pergunta!r}")
    print(f"base: {len(motor.artigos)} artigos\n")

    classificador = intencoes.obter()
    intencao, confianca = classificador.prever(pergunta)
    print("CLASSIFICADOR")
    print(f"  intenção  : {intencao}")
    print(f"  confiança : {confianca:.3f} (limiar {LIMIAR_CONFIANCA})")
    if classificador.carregado:
        probabilidades = sorted(classificador.probabilidades(pergunta).items(),
                                key=lambda p: -p[1])
        print("  probabilidades: " + ", ".join(f"{i}={p:.3f}" for i, p in probabilidades))

    termos = motor._termos_consulta(pergunta)
    conceitos, soltos = motor._conceitos(termos)
    print("\nTERMOS DA PERGUNTA")
    print(f"  temáticos  : {sorted(termos)}")
    print(f"  conceitos  : {[list(c) for c in conceitos]}")
    print(f"  soltos     : {sorted(soltos)}")
    for termo in sorted(termos):
        variantes = sorted({termo} | recuperacao.ALIASES.get(termo, set()))
        print(f"  variantes de '{termo}': {variantes}")

    area = motor.detetar_area(pergunta)
    print(f"\nÁREA DETECTADA: {area}")

    print("\nCANDIDATOS (sem guarda de cobertura, para ver o que seria ranqueado)")
    for c in motor.buscar(pergunta, k=8, cobertura_minima=0.0):
        a = c.artigo
        cob = motor._cobertura(pergunta, a, termos)
        print(f"  {c.score:.4f} sim={c.similaridade:.4f} cob={cob:.3f} [{a.get('area')}] "
              f"{(a.get('titulo') or '')[:66]}")

    guarda = 0.0 if sem_guarda else COBERTURA_MINIMA
    finais = motor.buscar(pergunta, k=5, cobertura_minima=guarda)
    print(f"\nRESULTADO FINAL (cobertura >= {guarda}, score >= {LIMIAR_SCORE})")
    if not finais:
        print("  nenhum artigo recomendado -> o fluxo deve se abster")
    for c in finais:
        a = c.artigo
        print(f"  {c.score:.4f} [{a.get('area')}] {(a.get('titulo') or '')[:66]}")

    print("\nCOBERTURA DOS 5 MELHORES (sem guarda), por área")
    for c in motor.buscar(pergunta, k=5, cobertura_minima=0.0):
        a = c.artigo
        alvo = recuperacao.sem_acento(" ".join([
            a.get("titulo") or "", a.get("resumo") or "",
            " ".join(a.get("palavras_chave") or []),
        ]))
        detalhe = []
        for termo in sorted(termos):
            # equivalentes() = ALIASES + glossário; só o ALIASES dava "NAO" falso
            variantes = sorted({termo} | recuperacao.equivalentes(termo))
            casou = [v for v in variantes if motor._contem(alvo, v)]
            detalhe.append(f"{termo}={'sim' if casou else 'NAO'}({','.join(casou)})")
        print(f"  [{a.get('area')}] {' '.join(detalhe)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    investigar(sys.argv[1], "--sem-guarda" in sys.argv)

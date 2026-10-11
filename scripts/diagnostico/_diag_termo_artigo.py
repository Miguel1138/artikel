"""Mostra, para uma pergunta, quais termos (ou equivalentes) casaram em cada artigo.

Uso: python scripts/diagnostico/_diag_termo_artigo.py "preciso de artigos sobre física quântica"
"""
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "app"))

from recuperacao import ALIASES, Motor, sem_acento  # noqa: E402


def main() -> None:
    consulta = sys.argv[1] if len(sys.argv) > 1 else "preciso de artigos sobre física quântica"
    motor = Motor()
    termos = motor._termos_consulta(consulta)
    print(f"consulta: {consulta!r}")
    print(f"termos temáticos: {sorted(termos)}\n")

    for candidato in motor.buscar(consulta, k=3, cobertura_minima=0.0):
        artigo = candidato.artigo
        alvo = sem_acento(" ".join([
            artigo.get("titulo") or "", artigo.get("resumo") or "",
            " ".join(artigo.get("palavras_chave") or []),
        ]))
        print(f"[{artigo.get('area')}] {(artigo.get('titulo') or '')[:70]}")
        print(f"  score {candidato.score:.3f} | cobertura "
              f"{motor._cobertura(consulta, artigo, termos):.3f}")
        for termo in sorted(termos):
            variantes = sorted({termo} | ALIASES.get(termo, set()))
            casadas = [v for v in variantes if motor._contem(alvo, v)]
            print(f"  termo {termo!r}: casou via {casadas or 'NADA'}")
            for variante in casadas:
                for m in re.finditer(
                    rf"(?<![0-9a-z]){re.escape(variante)}(?:s|es)?(?![0-9a-z])", alvo
                ):
                    trecho = alvo[max(0, m.start() - 55):m.start() + 45]
                    print(f"      ...{trecho}...")
        print()


if __name__ == "__main__":
    main()

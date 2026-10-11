"""Mostra o trecho exato onde um termo casou num artigo (para achar falso positivo).

Uso: python scripts/diagnostico/_diag_trecho.py "quantica"
"""
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "app"))

from recuperacao import Motor, sem_acento  # noqa: E402


def main() -> None:
    termo = sys.argv[1] if len(sys.argv) > 1 else "quantica"
    motor = Motor()
    radical = termo[:5] if len(termo) > 4 else termo
    padrao = re.compile(rf"(?<![0-9a-z]){re.escape(radical)}")
    print(f"termo {termo!r} -> radical usado no casamento: {radical!r}\n")

    achados = 0
    for artigo in motor.artigos:
        alvo = sem_acento(" ".join([
            artigo.get("titulo") or "", artigo.get("resumo") or "",
            " ".join(artigo.get("palavras_chave") or []),
        ]))
        for m in padrao.finditer(alvo):
            inicio = max(0, m.start() - 45)
            # a "palavra" completa que casou, até o próximo separador
            fim = m.start()
            while fim < len(alvo) and alvo[fim].isalnum():
                fim += 1
            palavra = alvo[m.start():fim]
            achados += 1
            if achados <= 12:
                print(f"[{artigo.get('area')}] palavra casada = {palavra!r}")
                print(f"    ...{alvo[inicio:fim]}...")
    print(f"\ntotal de casamentos de {radical!r}: {achados}")
    if achados:
        palavras = set()
        for artigo in motor.artigos:
            alvo = sem_acento(" ".join([
                artigo.get("titulo") or "", artigo.get("resumo") or "",
                " ".join(artigo.get("palavras_chave") or []),
            ]))
            for m in padrao.finditer(alvo):
                fim = m.start()
                while fim < len(alvo) and alvo[fim].isalnum():
                    fim += 1
                palavras.add(alvo[m.start():fim])
        print(f"palavras distintas que casaram: {sorted(palavras)}")


if __name__ == "__main__":
    main()

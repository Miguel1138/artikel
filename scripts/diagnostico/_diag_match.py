"""Mostra por que um artigo casou com uma pergunta (depuração da recuperação).

Uso:
    python scripts/diagnostico/_diag_match.py "clareamento dental" YouTube
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "app"))

from recuperacao import ALIASES, Motor, sem_acento  # noqa: E402


def explicar(consulta: str, trecho_titulo: str) -> None:
    motor = Motor()
    termos = motor._termos_consulta(consulta)
    print(f"consulta: {consulta}")
    print(f"termos temáticos: {sorted(termos)}")
    for artigo in motor.artigos:
        if trecho_titulo.lower() not in (artigo.get("titulo") or "").lower():
            continue
        alvo = sem_acento(" ".join([
            artigo.get("titulo") or "",
            artigo.get("resumo") or "",
            " ".join(artigo.get("palavras_chave") or []),
        ]))
        print(f"\nartigo: {artigo['titulo'][:80]}")
        print(f"  area={artigo.get('area')} periodico={artigo.get('periodico')}")
        print(f"  palavras-chave: {artigo.get('palavras_chave')}")
        for termo in sorted(termos):
            variantes = {termo} | ALIASES.get(termo, set())
            for v in sorted(variantes):
                i = alvo.find(v[:5])
                if i >= 0:
                    print(f"  casou '{termo}' via '{v}': ...{alvo[max(0, i - 70):i + 70]}...")
                    break


if __name__ == "__main__":
    consulta = sys.argv[1] if len(sys.argv) > 1 else "clareamento dental"
    trecho = sys.argv[2] if len(sys.argv) > 2 else "YouTube"
    explicar(consulta, trecho)

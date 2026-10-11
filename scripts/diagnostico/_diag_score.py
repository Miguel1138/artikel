"""Decompõe o score de um candidato: quanto é similaridade e quanto é bônus de curadoria.

Uso: python scripts/diagnostico/_diag_score.py "preciso de artigos sobre computação quântica"
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "app"))

from recuperacao import Motor  # noqa: E402


def main() -> None:
    consulta = sys.argv[1] if len(sys.argv) > 1 else "preciso de artigos sobre computação quântica"
    motor = Motor()
    termos = motor._termos_consulta(consulta)
    print(f"consulta: {consulta!r}")
    print(f"termos temáticos: {sorted(termos)}")
    print(f"limiar de score: 0.1 | cobertura mínima: 0.34\n")

    for c in motor.buscar(consulta, k=8, cobertura_minima=0.0):
        a = c.artigo
        bonus = c.score - c.similaridade
        cobertura = motor._cobertura(consulta, a, termos)
        print(f"score {c.score:.4f} = similaridade {c.similaridade:.4f} + bônus {bonus:.4f}")
        print(f"   cobertura {cobertura:.4f} | área {a.get('area')} | {(a.get('titulo') or '')[:58]}")
        print(f"   motivos: {'; '.join(c.motivos) or '(nenhum)'}")
        # quais termos da pergunta aparecem de fato no artigo
        alvo = " ".join([a.get("titulo") or "", a.get("resumo") or "",
                         " ".join(a.get("palavras_chave") or [])])
        presentes = [t for t in sorted(termos) if motor._contem(alvo, t)]
        print(f"   termos presentes no artigo: {presentes or 'NENHUM'}")
        print()


if __name__ == "__main__":
    main()

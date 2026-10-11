"""Diagnóstico da recuperação sobre a base curada (não faz parte do pipeline nem da API).

Uso:
    python scripts/diagnostico/_diag_recuperacao.py
    python scripts/diagnostico/_diag_recuperacao.py "preciso de artigos sobre clareamento dental"
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "app"))

from recuperacao import Motor, sem_acento  # noqa: E402

PERGUNTAS = [
    "preciso de artigos sobre clareamento dental",
    "Tem estudos recentes sobre clareamento dental?",
    "Quero artigos sobre ansiedade em universitários",
    "preciso de artigos sobre segurança da informação",
    "preciso de artigos sobre implantes dentários",
    "preciso de artigos sobre astrofísica de neutrinos",
]

# Termos que deveriam aparecer nos resultados de cada pergunta (checagem de recall).
RELEVANTES = {
    "clareamento": ["clareamento", "whiten", "bleach"],
    "ansiedade": ["ansiedade", "anxiety"],
    "segurança": ["security", "seguranca", "privacidade", "privacy"],
    "implantes": ["implant", "implante"],
}


def mostrar(motor: Motor, consulta: str, cobertura: float) -> None:
    termos = motor._termos_consulta(consulta)
    print(f"\nQ: {consulta}")
    print(f"   termos temáticos: {sorted(termos)} | cobertura mínima {cobertura}")
    candidatos = motor.buscar(consulta, cobertura_minima=cobertura)
    if not candidatos:
        print("   (nenhum candidato)")
        return
    for c in candidatos[:5]:
        cob = motor._cobertura(consulta, c.artigo, termos)
        titulo = (c.artigo.get("titulo") or "")[:52]
        print(f"   {c.score:.3f} sim={c.similaridade:.3f} cob={cob:.2f} | {titulo}")

    # Recall: quantos artigos do tema existem na base e quantos entraram no top 5.
    for chave, marcadores in RELEVANTES.items():
        if not any(chave in sem_acento(consulta) for chave in [chave]):
            continue
        do_tema = [
            a for a in motor.artigos
            if any(m in sem_acento(" ".join([
                a.get("titulo") or "", a.get("resumo") or "",
                " ".join(a.get("palavras_chave") or [])])) for m in marcadores)
        ]
        no_top = [c for c in candidatos if c.artigo in do_tema]
        print(f"   recall do tema '{chave}': {len(no_top)}/{min(5, len(do_tema))} do top 5 "
              f"(base tem {len(do_tema)} artigos do tema)")

if __name__ == "__main__":
    motor = Motor()
    print(f"base: {len(motor.artigos)} artigos, {len(motor.periodicos())} periódicos")
    perguntas = sys.argv[1:] or PERGUNTAS
    for cobertura in (0.5, 0.34):
        print("\n" + "=" * 70)
        print(f"COBERTURA MÍNIMA = {cobertura}")
        print("=" * 70)
        for q in perguntas:
            mostrar(motor, q, cobertura)

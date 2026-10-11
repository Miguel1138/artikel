"""Varre variações de uma pergunta e mostra o que o fluxo devolve em cada uma.

Uso:
    python scripts/diagnostico/_diag_retornos.py
    python scripts/diagnostico/_diag_retornos.py "computação quântica"

O critério de suspeita é **relevância**, não área: um artigo é suspeito quando não contém
os termos temáticos da pergunta. Comparar por área engana — "física quântica" não detecta
área nenhuma, e a checagem por área dava "ok" para um artigo de Psicologia devolvido nessa
busca.
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "app"))

import fluxo  # noqa: E402
import recuperacao  # noqa: E402

TEMAS = [
    "computação quântica",
    "quântica",
    "computação",
    "física quântica",
    "criptografia quântica",
    "direito penal",
    "engenharia civil",
    "medicina veterinária",
]

FORMULACOES = [
    "{t}",
    "preciso de artigos sobre {t}",
    "quero artigos sobre {t}",
    "tem estudos recentes sobre {t}?",
    "me indica referências sobre {t}",
]

# Cobertura abaixo disto é considerada fora do tema (mesmo valor usado na recuperação).
COBERTURA_MINIMA = 0.34


def main() -> None:
    temas = [sys.argv[1]] if len(sys.argv) > 1 else TEMAS
    motor = recuperacao.obter()

    print("Verificação dos retornos do fluxo")
    print("(suspeito = devolveu artigo sem os termos da pergunta)\n")
    problemas = 0
    total = 0
    for tema in temas:
        for molde in FORMULACOES:
            total += 1
            pergunta = molde.format(t=tema)
            r = fluxo.responder(pergunta, sessao="diagnostico-" + tema)
            termos = motor._termos_consulta(pergunta)
            coberturas = [
                motor._cobertura(pergunta, motor.por_id(a.id) or {}, termos)
                for a in r.artigos
            ]
            minima = min(coberturas) if coberturas else None
            suspeito = bool(r.artigos) and minima is not None and minima < COBERTURA_MINIMA
            if suspeito:
                problemas += 1
            marca = "SUSPEITO" if suspeito else "ok      "
            valor = f"{minima:.2f}" if minima is not None else "-"
            print(f"{marca} {pergunta[:50]:<52} -> {r.tipo:<17} {len(r.artigos)} art. "
                  f"cobertura mínima={valor}")
            for a, cob in zip(r.artigos, coberturas):
                if cob < COBERTURA_MINIMA:
                    print(f"          cobertura {cob:.2f} [{a.area}] {a.titulo[:54]}")

    print(f"\n{problemas} de {total} casos devolveram artigo fora do tema da pergunta")


if __name__ == "__main__":
    main()

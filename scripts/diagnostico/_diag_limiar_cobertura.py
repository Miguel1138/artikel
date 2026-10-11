"""Compara limiares de cobertura: quantos artigos cada pergunta devolve em cada valor.

Uso: python scripts/diagnostico/_diag_limiar_cobertura.py

Serve para escolher o limiar sem achismo: mostra de um lado as perguntas que devem
funcionar (têm artigo na base) e do outro as que não têm nada a ver com o recorte.
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "app"))

from recuperacao import Motor  # noqa: E402

# Perguntas que devem achar artigo (assunto presente na base curada).
DEVEM_ACHAR = [
    "preciso de artigos sobre clareamento dental",
    "Quero artigos sobre ansiedade em universitários",
    "preciso de artigos sobre implantes dentários",
    "cadê artigos sobre periodontia",
    "preciso de artigos sobre segurança da informação",
    "Preciso de artigos sobre aprendizado de máquina na saúde",
    "preciso de artigos sobre depressão em adolescentes",
    "preciso de artigos sobre desenvolvimento infantil",
    "Tem estudos recentes sobre clareamento dental?",
    "me dá referências sobre saúde mental no trabalho",
]

# Perguntas fora do recorte: o correto é abster (devolver zero).
NAO_DEVEM_ACHAR = [
    "preciso de artigos sobre computação quântica",
    "preciso de artigos sobre física quântica",
    "preciso de artigos sobre criptografia quântica",
    "preciso de artigos sobre direito penal",
    "preciso de artigos sobre engenharia civil",
    "preciso de artigos sobre medicina veterinária",
]

LIMIARES = [0.34, 0.5, 0.6, 0.75, 1.0]


def main() -> None:
    motor = Motor()
    print(f"base: {len(motor.artigos)} artigos\n")

    cabecalho = f"{'pergunta':<50} " + " ".join(f"{l:>6}" for l in LIMIARES)
    print("DEVEM ACHAR ARTIGO (número de artigos devolvidos)")
    print(cabecalho)
    for pergunta in DEVEM_ACHAR:
        contagens = [len(motor.buscar(pergunta, cobertura_minima=l)) for l in LIMIARES]
        print(f"{pergunta[:48]:<50} " + " ".join(f"{c:>6}" for c in contagens))

    print("\nNÃO DEVEM ACHAR (o correto é zero)")
    print(cabecalho)
    for pergunta in NAO_DEVEM_ACHAR:
        contagens = [len(motor.buscar(pergunta, cobertura_minima=l)) for l in LIMIARES]
        print(f"{pergunta[:48]:<50} " + " ".join(f"{c:>6}" for c in contagens))

    print("\nResumo: para cada limiar, quantas perguntas legítimas ficariam sem resposta")
    for limite in LIMIARES:
        vazias = [p for p in DEVEM_ACHAR if not motor.buscar(p, cobertura_minima=limite)]
        intrusas = [p for p in NAO_DEVEM_ACHAR if motor.buscar(p, cobertura_minima=limite)]
        print(f"  {limite:<5} legítimas sem resposta: {len(vazias)} | "
              f"fora do tema respondidas: {len(intrusas)}")
        for p in vazias:
            print(f"        sem resposta: {p}")
        for p in intrusas:
            print(f"        intrusa:      {p}")


if __name__ == "__main__":
    main()

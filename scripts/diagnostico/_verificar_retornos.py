"""Confere o retorno do chatbot para perguntas de dentro e de fora do escopo da base.

Fala com a API real (não com as funções internas), que é o caminho que o usuário usa.

Uso: python scripts/diagnostico/_verificar_retornos.py [http://127.0.0.1:8000]
"""
import json
import sys
import urllib.error
import urllib.request

DEVE_RECOMENDAR = [
    "Preciso de artigos sobre aprendizado de máquina na saúde",
    "Quero artigos sobre ansiedade em universitários",
    "Tem estudos recentes sobre clareamento dental?",
    "preciso de artigos sobre implantes dentários",
    "preciso de artigos sobre segurança da informação",
    "me dá referências sobre saúde mental no trabalho",
]

NAO_DEVE_RECOMENDAR = [
    "preciso de artigos sobre computação quântica",
    "quero artigos sobre computação quântica",
    "preciso de artigos sobre física quântica",
    "preciso de artigos sobre criptografia quântica",
    "preciso de artigos sobre direito penal",
    "preciso de artigos sobre engenharia civil",
    "preciso de artigos sobre medicina veterinária",
    "preciso de artigos sobre astrofísica de neutrinos",
]


def chamar(base, caminho, dados=None):
    # `dados is not None` e não `if dados`: um corpo vazio ({}) é falsy e a limpeza de
    # sessão sairia como GET, que a rota não aceita.
    metodo = "POST" if dados is not None else "GET"
    req = urllib.request.Request(
        base + caminho,
        data=json.dumps(dados).encode("utf-8") if dados is not None else None,
        headers={"Content-Type": "application/json"},
        method=metodo,
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def main() -> None:
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    try:
        chamar(base, "/saude")
    except urllib.error.URLError as exc:
        raise SystemExit(f"API não respondeu em {base}: {exc}")

    falhas = 0
    print("Perguntas que DEVEM trazer artigo\n")
    for pergunta in DEVE_RECOMENDAR:
        r = chamar(base, "/chat", {"mensagem": pergunta, "sessao": "retornos"})
        ok = bool(r["artigos"])
        falhas += 0 if ok else 1
        areas = sorted({a["area"] for a in r["artigos"]})
        print(f"  {'ok   ' if ok else 'FALHA'} {pergunta[:50]:<52} {r['tipo']:<14} "
              f"{len(r['artigos'])} art. {areas}")

    print("\nPerguntas que NÃO devem trazer artigo (tema ausente da base)\n")
    for pergunta in NAO_DEVE_RECOMENDAR:
        r = chamar(base, "/chat", {"mensagem": pergunta, "sessao": "retornos"})
        ok = not r["artigos"]
        falhas += 0 if ok else 1
        detalhe = ""
        if not ok:
            detalhe = " -> " + "; ".join(
                f"[{a['area']}] {a['titulo'][:34]}" for a in r["artigos"][:2])
        print(f"  {'ok   ' if ok else 'FALHA'} {pergunta[:50]:<52} {r['tipo']:<14} "
              f"{len(r['artigos'])} art.{detalhe}")

    chamar(base, "/sessao/retornos/limpar", {})
    print(f"\n{'todos os retornos corretos' if not falhas else str(falhas) + ' retorno(s) errado(s)'}")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()

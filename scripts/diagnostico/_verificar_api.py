"""Verificação de ponta a ponta da API do Artikel (sem dependências além da stdlib).

Uso (com a API no ar):
    python scripts/diagnostico/_verificar_api.py [porta]

Percorre as 11 perguntas simuladas do Marco 1 e imprime, para cada uma, a intenção, a ação,
o traço da decisão e o começo da resposta. Serve para a demonstração do Marco 6.
"""
import json
import sys
import urllib.error
import urllib.request

PERGUNTAS = [
    "Preciso de artigos sobre aprendizado de máquina na saúde",
    "A revista X é confiável?",
    "Como procuro artigos no SciELO?",
    "Quero artigos sobre ansiedade em universitários",
    "Tem estudos recentes sobre clareamento dental?",
    "Posso citar a Wikipédia no meu TCC?",
    "Que palavras-chave uso para achar artigos sobre cárie infantil?",
    "Qual remédio tomar para ansiedade?",
    "Ajuste o meu texto",
]
# A 3 depende de contexto: é pedida depois de uma busca.
DEPOIS_DA_BUSCA = "referência ABNT do segundo artigo"


def chamar(base, caminho, dados=None):
    req = urllib.request.Request(
        base + caminho,
        data=json.dumps(dados).encode("utf-8") if dados else None,
        headers={"Content-Type": "application/json"},
        method="POST" if dados else "GET",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    porta = sys.argv[1] if len(sys.argv) > 1 else "8000"
    base = f"http://127.0.0.1:{porta}"

    try:
        saude = chamar(base, "/saude")
    except urllib.error.URLError as exc:
        raise SystemExit(f"API não respondeu em {base}: {exc}")

    print("ESTADO DA API")
    print(json.dumps(saude, ensure_ascii=False, indent=2), "\n")

    sessao = "verificacao"
    for pergunta in PERGUNTAS:
        r = chamar(base, "/chat", {"mensagem": pergunta, "sessao": sessao})
        t = r["traco"]
        print(f"P: {pergunta}")
        print(f"   intenção={r['intencao']} ({t['confianca']}) | tipo={r['tipo']} | "
              f"ação={t['acao']} | regra={t['regra']}")
        print(f"   resposta: {r['resposta'][:150].replace(chr(10), ' ')}")
        for a in r["artigos"][:3]:
            print(f"     {a['posicao']}. [{a['score']}] {a['titulo'][:58]}")
            print(f"        {a['referencia_abnt'][:118]}")
        print()

    # Contexto (R1): a mesma sessão guarda a última lista exibida.
    r = chamar(base, "/chat", {"mensagem": "preciso de artigos sobre clareamento dental",
                               "sessao": sessao})
    print(f"P: preciso de artigos sobre clareamento dental -> {len(r['artigos'])} artigos")
    print(f"   ABNT do 1º: {r['artigos'][0]['referencia_abnt'][:130] if r['artigos'] else '—'}")
    r = chamar(base, "/chat", {"mensagem": DEPOIS_DA_BUSCA, "sessao": sessao})
    print(f"P: {DEPOIS_DA_BUSCA}")
    print(f"   tipo={r['tipo']} | contexto usado={r['traco']['contexto_usado']}")
    print(f"   {r['resposta'][:220].replace(chr(10), ' ')}")


if __name__ == "__main__":
    main()

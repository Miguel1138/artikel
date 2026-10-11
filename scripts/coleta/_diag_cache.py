"""Diagnóstico do cache da coleta: mostra a forma dos arquivos de data/raw.

Uso:
    python scripts/coleta/_diag_cache.py                 # resumo por fonte
    python scripts/coleta/_diag_cache.py doaj            # detalhe de uma fonte
    python scripts/coleta/_diag_cache.py doaj periodicos_computacao_cc
"""
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DIR_RAW = RAIZ / "data" / "raw"


def resumo():
    print(f"{'fonte':14} {'arquivos':>9} {'tamanho':>10}  formas")
    for pasta in sorted(p for p in DIR_RAW.iterdir() if p.is_dir()):
        arquivos = sorted(pasta.glob("*.json"))
        total = sum(a.stat().st_size for a in arquivos)
        formas = {}
        for a in arquivos[:400]:
            try:
                dados = json.loads(a.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                formas["ILEGIVEL"] = formas.get("ILEGIVEL", 0) + 1
                continue
            forma = f"{type(dados).__name__}"
            if isinstance(dados, list) and dados:
                forma += f"[{type(dados[0]).__name__}]"
            elif isinstance(dados, dict):
                forma += "{" + ",".join(sorted(dados)[:3]) + "}"
            formas[forma] = formas.get(forma, 0) + 1
        print(f"{pasta.name:14} {len(arquivos):9d} {total/1e6:9.2f}M  "
              + ", ".join(f"{k} x{v}" for k, v in sorted(formas.items())))


def detalhe(fonte, nome=None):
    pasta = DIR_RAW / fonte
    if not pasta.exists():
        raise SystemExit(f"fonte inexistente: {pasta}")
    alvos = sorted(pasta.glob(f"{nome}.json")) if nome else sorted(pasta.glob("*.json"))[:5]
    for a in alvos:
        dados = json.loads(a.read_text(encoding="utf-8"))
        print(f"\n=== {a.name} ({a.stat().st_size} bytes) ===")
        print("forma:", type(dados).__name__,
              f"| itens: {len(dados)}" if hasattr(dados, "__len__") else "")
        amostra = dados[:1] if isinstance(dados, list) else dados
        print(json.dumps(amostra, ensure_ascii=False)[:700])


if __name__ == "__main__":
    if len(sys.argv) == 1:
        resumo()
    else:
        detalhe(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)

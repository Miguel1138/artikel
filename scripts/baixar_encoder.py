"""Baixa o encoder de sentenças usado pelo classificador de intenções para models/encoder/.

Modelo: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 (Apache-2.0, 50+ idiomas,
inclui português), versão ONNX quantizada. Roda local em CPU; depois do download não usa rede.

    pip install onnxruntime tokenizers
    python scripts/baixar_encoder.py            # ~128 MB
    python scripts/baixar_encoder.py --completo # modelo fp32 (~470 MB), sem exigir AVX2
"""
from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "app"))

from config import ARQ_ENCODER  # noqa: E402

REPO = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
BASE = f"https://huggingface.co/{REPO}/resolve/main/"
# origem no repositório -> destino em models/encoder/
ARQUIVOS = {
    "onnx/model_quint8_avx2.onnx": "model.onnx",
    "tokenizer.json": "tokenizer.json",
    "config.json": "config.json",
    "1_Pooling/config.json": "1_Pooling/config.json",
}


def baixar(origem: str, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(BASE + origem, headers={"User-Agent": "artikel"})
    with urllib.request.urlopen(req, timeout=120) as resp, open(destino, "wb") as fh:
        while bloco := resp.read(1 << 20):
            fh.write(bloco)
    print(f"  {origem:<32} -> {destino.relative_to(RAIZ)}  ({destino.stat().st_size / 1e6:.1f} MB)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--completo", action="store_true", help="modelo fp32 (470 MB) em vez do quantizado")
    ap.add_argument("--forcar", action="store_true", help="baixa de novo mesmo se já existir")
    args = ap.parse_args()

    arquivos = dict(ARQUIVOS)
    if args.completo:
        arquivos = {("onnx/model.onnx" if k.startswith("onnx/") else k): v for k, v in arquivos.items()}
    pendentes = {o: d for o, d in arquivos.items() if args.forcar or not (ARQ_ENCODER / d).exists()}
    if not pendentes:
        print(f"encoder já presente em {ARQ_ENCODER.relative_to(RAIZ)}/ (use --forcar para baixar de novo)")
        return
    print(f"baixando {len(pendentes)} arquivo(s) de huggingface.co/{REPO}")
    for origem, destino in pendentes.items():
        baixar(origem, ARQ_ENCODER / destino)


if __name__ == "__main__":
    main()

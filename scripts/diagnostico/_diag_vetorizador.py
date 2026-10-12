"""Compara vetorizadores (TF-IDF, Bag of Words) e tratamento de stopwords no classificador.

Uso: python scripts/diagnostico/_diag_vetorizador.py

Para cada combinação mede (1) validação cruzada repetida (4 partições x 5 rodadas) sobre
`data/intents.csv` e (2) acurácia em `tests/casos_teste.csv`, que nunca entra no treino.
Os dois números juntos importam: com 30 casos o teste sozinho oscila 3 pontos por caso.

"stopwords do projeto (acento corrigido)" mostra o que mudaria se "não", "você", "também"
e "até" fossem de fato removidos: hoje a lista tem a forma acentuada, o token sai sem
acento, e eles nunca casam (ver `app/preprocessamento.py`).
"""
import csv
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "app"))

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import RepeatedStratifiedKFold, cross_val_score
from sklearn.pipeline import make_pipeline

import preprocessamento as pp
from config import ARQ_CASOS, ARQ_INTENTS, SEED
from preprocessador_generico import Preprocessador, criar_vetorizador

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def ler(caminho: Path, col_texto: str, col_rotulo: str) -> tuple[list[str], list[str]]:
    with caminho.open(encoding="utf-8", newline="") as fh:
        linhas = [l for l in csv.DictReader(fh) if (l.get(col_texto) or "").strip()]
    return [l[col_texto].strip() for l in linhas], [l[col_rotulo].strip() for l in linhas]


PREPROCESSADORES = {
    "atual (normalizar)": pp.normalizar,
    "sem remover stopwords": lambda t: pp.normalizar(t, remover_stopwords=False),
    "stopwords do projeto (acento corrigido)": Preprocessador(
        stopwords=pp.STOPWORDS, preservar=pp.NUCLEARES, remover_urls=False, remover_html=False
    ),
}


def main() -> None:
    X, y = ler(ARQ_INTENTS, "frase", "intencao")
    Xt, yt = ler(ARQ_CASOS, "pergunta", "intencao_esperada")
    cv = RepeatedStratifiedKFold(n_splits=4, n_repeats=5, random_state=SEED)

    print(f"{len(X)} frases de treino, {len(Xt)} casos de teste\n")
    print(f"{'pré-processamento':<42} {'vetorizador':<12} {'n-gramas':<9} {'CV':>6} {'teste':>6}  erros no teste")
    for nome_pre, pre in PREPROCESSADORES.items():
        for tipo in ("tfidf", "bow", "bow_binario"):
            for ng in ((1, 1), (1, 2)):
                pipe = make_pipeline(
                    criar_vetorizador(tipo, pre, ngramas=ng),
                    LogisticRegression(max_iter=2000, C=8.0, class_weight="balanced", random_state=SEED),
                )
                cv_medio = cross_val_score(pipe, X, y, cv=cv).mean()
                pipe.fit(X, y)
                previsto = pipe.predict(Xt)
                acerto = float(np.mean([p == r for p, r in zip(previsto, yt)]))
                erros = [i + 1 for i, (p, r) in enumerate(zip(previsto, yt)) if p != r]
                print(f"{nome_pre:<42} {tipo:<12} {str(ng):<9} {cv_medio:6.3f} {acerto:6.3f}  linhas {erros}")


if __name__ == "__main__":
    main()

# Diagnóstico

Scripts de apoio para **entender** o comportamento do Artikel. Não fazem parte do pipeline
nem da API: nenhum deles é importado pelo sistema, e todos podem ser apagados sem afetar o
funcionamento.

Servem para a demonstração (explicar uma decisão do bot na hora) e para investigar quando
algo parece errado.

| Script | Para quê | Uso |
|---|---|---|
| `_verificar_api.py` | percorre as 11 perguntas simuladas contra a API no ar e imprime intenção, ação, traço e resposta | `python scripts/diagnostico/_verificar_api.py 8000` |
| `_diag_recuperacao.py` | ranqueamento e recall por pergunta, com a cobertura de cada artigo | `python scripts/diagnostico/_diag_recuperacao.py` |
| `_diag_match.py` | mostra por que **um** artigo casou com uma pergunta (qual termo, em que texto) | `python scripts/diagnostico/_diag_match.py "clareamento dental" YouTube` |
| `_diag_cache.py` | forma e tamanho dos arquivos de `data/raw`, por fonte | `python scripts/diagnostico/_diag_cache.py doaj` |
| `_diag_determinismo.py` | roda a avaliação N vezes e acusa número que muda sozinho | `python scripts/diagnostico/_diag_determinismo.py 8` |

Os dois primeiros exigem a base curada (`data/knowledge_base.json`) e, no caso do
`_verificar_api.py`, a API no ar:

```bash
uvicorn main:app --app-dir app --port 8000     # em outro terminal
```

As verificações que fazem parte da entrega (e que valem como teste) estão em
`tests/` e em `web/_verificar_*.js` — ver o README.

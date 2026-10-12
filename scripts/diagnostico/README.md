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
| `_verificar_retornos.py` | confere, contra a API no ar, o que o bot devolve para perguntas de dentro e de fora do escopo | `python scripts/diagnostico/_verificar_retornos.py 8000` |
| `_diag_pergunta.py` | abre uma pergunta: intenção, área, termos, candidatos e cobertura | `python scripts/diagnostico/_diag_pergunta.py "computação quântica"` |
| `_diag_score.py` | decompõe o score em similaridade e bônus de curadoria | `python scripts/diagnostico/_diag_score.py "computação quântica"` |
| `_diag_termo_artigo.py` | mostra qual termo (ou equivalente) casou em cada artigo e onde | `python scripts/diagnostico/_diag_termo_artigo.py "física quântica"` |
| `_diag_trecho.py` | procura o trecho exato de um termo, para achar falso positivo | `python scripts/diagnostico/_diag_trecho.py quantica` |
| `_diag_retornos.py` | varre variações de uma pergunta e acusa retorno fora do tema | `python scripts/diagnostico/_diag_retornos.py` |
| `_diag_limiar_cobertura.py` | compara limiares de cobertura em perguntas de dentro e de fora do escopo | `python scripts/diagnostico/_diag_limiar_cobertura.py` |
| `_diag_vetorizador.py` | compara TF-IDF, Bag of Words (contagem e binário), n-gramas e tratamento de stopwords no classificador de intenções | `python scripts/diagnostico/_diag_vetorizador.py` |

Os dois primeiros exigem a base curada (`data/knowledge_base.json`) e, no caso do
`_verificar_api.py`, a API no ar:

```bash
uvicorn main:app --app-dir app --port 8000     # em outro terminal
```

As verificações que fazem parte da entrega (e que valem como teste) estão em
`tests/` e em `web/_verificar_*.js` — ver o README.

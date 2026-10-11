# Avaliação — Artikel

Casos em `tests/casos_teste.csv`: **30** (marco 5 do cronograma).

## Métricas

| Métrica | Resultado | Meta | Situação |
|---|---|---|---|
| Acurácia de intenções | 1.000 | 0.85 | OK |
| Precisão@5 da recuperação | 0.743 | 0.60 | OK |
| Abstenção correta fora de escopo | 1.000 | 0.90 | OK |
| Citações inventadas | 0 | 0 | OK |

## Matriz de confusão

| esperado \ previsto | buscar_referencias | avaliar_fonte | formatar_referencia | orientar_busca | fora_de_escopo |
|---|---|---|---|---|---|
| buscar_referencias | 7 | 0 | 0 | 0 | 1 |
| avaliar_fonte | 0 | 6 | 0 | 0 | 0 |
| formatar_referencia | 0 | 0 | 5 | 0 | 0 |
| orientar_busca | 0 | 0 | 0 | 5 | 0 |
| fora_de_escopo | 0 | 0 | 0 | 0 | 6 |

## Casos que não passaram

Nenhum.

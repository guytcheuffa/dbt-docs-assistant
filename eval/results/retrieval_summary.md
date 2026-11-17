# Recherche : résultats sur 78 questions avec réponse

Niveau page (URL sans ancre). R@k = part des questions dont une bonne page est dans le top k.

| Mode | R@1 | R@3 | R@5 | R@10 | MRR |
|---|---|---|---|---|---|
| dense | 0.56 | 0.74 | 0.91 | 0.94 | 0.69 |
| bm25 | 0.38 | 0.65 | 0.76 | 0.82 | 0.53 |
| hybrid | 0.55 | 0.77 | 0.83 | 0.94 | 0.68 |
| hybrid_rerank | 0.49 | 0.79 | 0.94 | 0.97 | 0.67 |

## Détail par groupe (R@5)

| Groupe | n | dense | bm25 | hybrid | hybrid_rerank |
|---|---|---|---|---|---|
| formulation = doc | 72 | 0.93 | 0.76 | 0.86 | 0.96 |
| formulation = user | 6 | 0.67 | 0.67 | 0.50 | 0.67 |
| type = comparison | 11 | 0.91 | 0.55 | 0.73 | 1.00 |
| type = fact | 29 | 0.97 | 0.86 | 0.97 | 0.97 |
| type = multi_page | 10 | 0.80 | 0.80 | 0.60 | 0.90 |
| type = procedure | 28 | 0.89 | 0.71 | 0.82 | 0.89 |

## Questions ratées par hybrid_rerank (bonne page absente du top 10)

- q072 : How can I limit the amount of data processed in development?
- q076 : How do I keep a history of how a customer's address changed over time?

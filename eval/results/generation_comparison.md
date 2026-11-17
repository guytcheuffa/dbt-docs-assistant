# Génération : comparaison avec un juge commun (`qwen3.8-flash`)

Même jeu (90 questions, dont 12 sans réponse), mêmes passages (`hybrid_rerank`, top 5), même juge.

| Configuration | Refus corrects (12) | Refus à tort (78) | Page attendue citée | Fidélité « oui » | Justesse « oui » | Longueur médiane |
|---|---|---|---|---|---|---|
| `qwen-flash`, consigne v1 (concise) | 12/12 | 1/78 | 66/77 (86 %) | 72/77 (5 partielles) | 63/77 (82 %) | 1 077 car. |
| `qwen3.8-flash`, consigne v1 (concise) | 12/12 | 2/78 | 68/76 (89 %) | 76/76 | 56/76 (74 %) | 994 car. |
| `qwen3.8-flash`, consigne v2 (complète) | 12/12 | 2/78 | 69/76 (91 %) | 75/76 (1 illisible) | 58/76 (76 %) | 1 510 car. |

Lecture :
- `qwen3.8-flash` n'ajoute aucune affirmation non appuyée par les passages ; `qwen-flash` en a 5 partiellement non appuyées.
- `qwen-flash` est jugé plus souvent « juste » par rapport à la référence ; une partie vient de connaissances hors passages, ce que le système doit éviter.
- La consigne v2 allonge les réponses de 50 % pour un gain faible (+2 réponses justes, +1 page attendue citée).
- Relecture manuelle d'un échantillon de « partielles » en v2 : surtout des réponses incomplètes par rapport à la référence (nuance de version, commande finale), rarement fausses ; le juge est sévère. q016 reste trop courte car le passage retrouvé ne contient pas le tableau des champs (limite de la recherche).

Configuration retenue : `qwen3.8-flash` + consigne v2 (fidélité maximale, meilleure citation de la page attendue).

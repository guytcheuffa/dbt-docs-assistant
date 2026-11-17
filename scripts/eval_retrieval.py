"""Étape 6a : mesure de la recherche sur le jeu d'évaluation (gratuit, tout en local).

Pour chaque question avec réponse et chaque mode (dense, bm25, hybrid, hybrid_rerank) :
- rappel@k : la bonne page est-elle dans les k premiers résultats ? (k = 1, 3, 5, 10)
- MRR : 1 / rang du premier résultat correct (0 s'il n'y en a pas dans le top 10)
La comparaison se fait au niveau de la page (URL sans ancre) ; les doublons `also_at` comptent.

Sorties : eval/results/retrieval_per_question.jsonl et eval/results/retrieval_summary.md
"""
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config
from src.retrieval.search import Retriever

MODES = ["dense", "bm25", "hybrid", "hybrid_rerank"]
KS = [1, 3, 5, 10]
OUT = config.ROOT / "eval" / "results"


def page(url):
    return url.split("#")[0].rstrip("/")


def first_hit_rank(hits, gold):
    for rank, h in enumerate(hits, 1):
        if {page(u) for u in [h["url"], *h.get("also_at", [])]} & gold:
            return rank
    return None


def main():
    questions = [json.loads(l) for l in open(config.ROOT / "eval" / "questions.jsonl", encoding="utf-8")]
    questions = [q for q in questions if q["answerable"]]
    r = Retriever()
    rows = []
    t0 = time.time()
    for n, q in enumerate(questions, 1):
        gold = {page(u) for u in q["gold_urls"]}
        row = {"id": q["id"], "type": q["type"], "phrasing": q.get("phrasing", "doc"), "question": q["question"]}
        for mode in MODES:
            hits = r.retrieve(q["question"], k=max(KS), mode=mode)
            row[mode] = {"rank": first_hit_rank(hits, gold), "top3": [h["url"] for h in hits[:3]]}
        rows.append(row)
        print(f"[{n}/{len(questions)}] {time.time() - t0:.0f}s  {q['id']}  "
              + "  ".join(f"{m}={row[m]['rank']}" for m in MODES), flush=True)

    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "retrieval_per_question.jsonl").open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def scores(subset):
        res = {}
        for mode in MODES:
            ranks = [row[mode]["rank"] for row in subset]
            res[mode] = {f"R@{k}": sum(1 for x in ranks if x and x <= k) / len(ranks) for k in KS}
            res[mode]["MRR"] = sum(1 / x for x in ranks if x) / len(ranks)
        return res

    groups = defaultdict(list)
    for row in rows:
        groups[f"type = {row['type']}"].append(row)
        groups[f"formulation = {row['phrasing']}"].append(row)

    lines = [f"# Recherche : résultats sur {len(rows)} questions avec réponse", "",
             "Niveau page (URL sans ancre). R@k = part des questions dont une bonne page est dans le top k.", "",
             "| Mode | R@1 | R@3 | R@5 | R@10 | MRR |", "|---|---|---|---|---|---|"]
    for mode, s in scores(rows).items():
        lines.append(f"| {mode} | " + " | ".join(f"{s[m]:.2f}" for m in ["R@1", "R@3", "R@5", "R@10", "MRR"]) + " |")
    lines += ["", "## Détail par groupe (R@5)", "", "| Groupe | n | " + " | ".join(MODES) + " |",
              "|---|---|" + "---|" * len(MODES)]
    for name, subset in sorted(groups.items()):
        s = scores(subset)
        lines.append(f"| {name} | {len(subset)} | " + " | ".join(f"{s[m]['R@5']:.2f}" for m in MODES) + " |")
    lines += ["", "## Questions ratées par hybrid_rerank (bonne page absente du top 10)", ""]
    for row in rows:
        if row["hybrid_rerank"]["rank"] is None:
            lines.append(f"- {row['id']} : {row['question']}")
    (OUT / "retrieval_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

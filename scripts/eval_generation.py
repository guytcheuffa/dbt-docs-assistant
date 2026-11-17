"""Étape 6b : qualité des réponses générées (payant, mais mis en cache et plafonné par TOKEN_BUDGET).

Pour chaque question du jeu d'évaluation (mode hybrid_rerank, 5 passages) :
- vérifié en local : refus ou non, citations présentes, page attendue citée, page attendue présente dans le contexte
- noté par un LLM juge (questions avec réponse, non refusées) :
    fidélité  = chaque affirmation est-elle appuyée par les passages fournis ? (yes / partial / no)
    justesse  = la réponse est-elle conforme à la réponse de référence ?       (yes / partial / no)

Options : --answer-model, --judge-model, --prompt (v1 | v2), --tag (suffixe des fichiers de sortie).
Sorties : eval/results/generation_per_question[_tag].jsonl et eval/results/generation_summary[_tag].md
Les passages retrouvés sont mis en cache (eval/results/hits_cache.json) : la recherche est déterministe.
"""
import argparse
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config
from src.generation.answer import Assistant, format_passages

OUT = config.ROOT / "eval" / "results"

JUDGE_PROMPT = """You are a strict evaluator of a question-answering system about dbt.
You receive a question, the documentation passages given to the system, the system's answer, and a reference answer.

Two separate checks:
1. Faithfulness: compare the SYSTEM ANSWER with the PASSAGES only. Ignore the reference answer for this check.
2. Correctness: compare the SYSTEM ANSWER with the REFERENCE ANSWER. A different but valid way to answer the question counts as correct if it is supported by the passages.

Return a JSON object with exactly these keys:
- "faithful": "yes" if every factual claim in the system answer is supported by the passages, "partial" if some claims are not supported, "no" if the main claims are not supported.
- "correct": "yes" if the system answer agrees with the reference answer on the essential points (or gives another valid answer), "partial" if it is incomplete or partly wrong, "no" if it is wrong or misses the point.
- "unsupported": a list of short quotes FROM THE SYSTEM ANSWER that are not supported by the passages, empty if none. Never quote the reference answer here.

Judge only what is written. Extra correct details supported by the passages are fine. Output only the JSON."""


def page(url):
    return url.split("#")[0].rstrip("/")


def judge(assistant, q, res, model):
    message = (f"Question: {q['question']}\n\nPassages:\n\n{format_passages(res['passages'])}\n\n"
               f"=====\nSystem answer:\n{res['answer']}\n\n=====\nReference answer:\n{q['reference_answer']}")
    text, usage, _ = assistant.chat(JUDGE_PROMPT, message, label=f"judge {q['id']}", model=model)
    m = re.search(r"\{.*\}", text, re.S)
    try:
        verdict = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        verdict = {}
    return {"faithful": verdict.get("faithful", "error"), "correct": verdict.get("correct", "error"),
            "unsupported": verdict.get("unsupported", []), "raw": text if not verdict else None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--answer-model", default=None, help="modèle qui répond (défaut : LLM_MODEL)")
    parser.add_argument("--judge-model", default=None, help="modèle juge (défaut : LLM_MODEL)")
    parser.add_argument("--prompt", default=config.PROMPT_VERSION, choices=["v1", "v2"])
    parser.add_argument("--tag", default="", help="suffixe des fichiers de sortie")
    args = parser.parse_args()
    suffix = f"_{args.tag}" if args.tag else ""

    questions = [json.loads(l) for l in open(config.ROOT / "eval" / "questions.jsonl", encoding="utf-8")]
    assistant = Assistant()
    answer_model = args.answer_model or assistant.model
    judge_model = args.judge_model or assistant.model
    print(f"Réponses : {answer_model} (consigne {args.prompt}) | juge : {judge_model} | "
          f"déjà consommé : {assistant.tokens_spent()} tokens", flush=True)
    hits_path = OUT / "hits_cache.json"
    hits_cache = json.loads(hits_path.read_text(encoding="utf-8")) if hits_path.exists() else {}
    rows, t0 = [], time.time()
    for n, q in enumerate(questions, 1):
        if q["question"] not in hits_cache:
            hits_cache[q["question"]] = assistant.retriever.retrieve(q["question"], k=config.TOP_K_CONTEXT)
            hits_path.write_text(json.dumps(hits_cache, ensure_ascii=False), encoding="utf-8")
        res = assistant.answer(q["question"], hits=hits_cache[q["question"]], model=answer_model, prompt=args.prompt)
        gold = {page(u) for u in q["gold_urls"]}
        row = {"id": q["id"], "type": q["type"], "answerable": q["answerable"], "question": q["question"],
               "answer": res["answer"], "refused": res["refused"],
               "n_citations": len(res["sources"]),
               "gold_in_context": bool(gold & {page(h["url"]) for h in res["passages"]}),
               "gold_cited": bool(gold & {page(s["url"]) for s in res["sources"]}),
               "sources": [s["url"] for s in res["sources"]]}
        if q["answerable"] and not res["refused"]:
            row["judge"] = judge(assistant, q, res, judge_model)
        rows.append(row)
        print(f"[{n}/{len(questions)}] {time.time() - t0:.0f}s {q['id']} refus={row['refused']} "
              f"juge={row.get('judge', {}).get('faithful', '-')}/{row.get('judge', {}).get('correct', '-')} "
              f"tokens={assistant.tokens_spent()}", flush=True)

    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / f"generation_per_question{suffix}.jsonl").open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    ans = [r for r in rows if r["answerable"]]
    noans = [r for r in rows if not r["answerable"]]
    judged = [r for r in ans if "judge" in r]
    pct = lambda a, b: f"{a}/{b} ({a / b:.0%})" if b else "-"
    faith = Counter(r["judge"]["faithful"] for r in judged)
    corr = Counter(r["judge"]["correct"] for r in judged)
    lines = [f"# Génération : résultats sur {len(rows)} questions", "",
             f"Réponses : `{answer_model}` (consigne {args.prompt}) ; recherche `hybrid_rerank`, "
             f"{config.TOP_K_CONTEXT} passages ; juge : `{judge_model}`. "
             f"Tokens consommés au total : {assistant.tokens_spent()}.", "",
             "## Refus", "",
             f"- Refus correct sur les questions sans réponse : {pct(sum(r['refused'] for r in noans), len(noans))}",
             f"- Refus à tort sur les questions avec réponse : {pct(sum(r['refused'] for r in ans), len(ans))}",
             f"  - dont page attendue absente du contexte (faute de la recherche) : "
             f"{sum(r['refused'] and not r['gold_in_context'] for r in ans)}", "",
             f"## Réponses données ({len(judged)} questions avec réponse, non refusées)", "",
             f"- Au moins une citation : {pct(sum(r['n_citations'] > 0 for r in judged), len(judged))}",
             f"- Page attendue citée : {pct(sum(r['gold_cited'] for r in judged), len(judged))}",
             f"- Fidélité aux passages (juge) : oui {faith['yes']}, partielle {faith['partial']}, non {faith['no']}"
             + (f", illisible {faith['error']}" if faith["error"] else ""),
             f"- Justesse vs référence (juge) : oui {corr['yes']}, partielle {corr['partial']}, non {corr['no']}"
             + (f", illisible {corr['error']}" if corr["error"] else ""), "",
             "## À relire", ""]
    for r in noans:
        if not r["refused"]:
            lines.append(f"- {r['id']} (sans réponse, NON refusée) : {r['question']}")
    for r in judged:
        if r["judge"]["faithful"] != "yes" or r["judge"]["correct"] != "yes":
            lines.append(f"- {r['id']} fidélité={r['judge']['faithful']} justesse={r['judge']['correct']} : {r['question']}")
    for r in ans:
        if r["refused"]:
            lines.append(f"- {r['id']} (refus à tort, page attendue dans le contexte : {r['gold_in_context']}) : {r['question']}")
    (OUT / f"generation_summary{suffix}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

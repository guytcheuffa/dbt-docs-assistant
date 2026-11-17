"""Contrôles automatiques sur data/processed/chunks.jsonl + 30 exemples à relire.
Usage : python scripts/check_chunks.py
"""
import json
import random
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
chunks = [json.loads(l) for l in (ROOT / "data/processed/chunks.jsonl").open(encoding="utf-8")]

fence_line = re.compile(r"^[ \t]*(`{3,}|~{3,})")
unbalanced = [c for c in chunks if sum(1 for l in c["text"].split("\n") if fence_line.match(l)) % 2]
tiny = [c for c in chunks if c["n_tokens"] < 30]
huge = [c for c in chunks if c["n_tokens"] > 600]
dups = [k for k, v in Counter(c["text"] for c in chunks).items() if v > 1]
no_anchor = sum("#" not in c["url"] for c in chunks)

print(f"{len(chunks)} passages")
print(f"fences déséquilibrées (code coupé) : {len(unbalanced)}")
print(f"passages < 30 tokens : {len(tiny)} | > 600 tokens : {len(huge)}")
print(f"textes en double : {len(dups)} | sans ancre d'URL : {no_anchor}")
print("par section :", dict(Counter(c['section'] for c in chunks).most_common()))
for name, lst in (("déséquilibrés", unbalanced), ("minuscules", tiny)):
    for c in lst[:3]:
        print(f"  {name}: {c['chunk_id']} ({c['n_tokens']})")

random.seed(42)
sample = random.sample(chunks, 25) + random.sample([c for c in chunks if c["has_code"]], 5)
with (ROOT / "data/processed/chunk_samples.md").open("w", encoding="utf-8") as f:
    for i, c in enumerate(sample, 1):
        f.write(f"\n\n==================== #{i} | {c['chunk_id']} | {c['n_tokens']} tokens ====================\n")
        f.write(f"URL : {c['url']}\nTITRES : {' > '.join(c['heading_path'])}\n\n{c['text']}\n")
print("exemples écrits dans data/processed/chunk_samples.md")

"""Compare rapidement les 4 modes de recherche sur quelques questions."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sys
import time

from src.retrieval.search import Retriever

QUESTIONS = [
    "how do I make an incremental model?",
    "what does the unique_key config do?",
    "how do I run only the models that changed?",
    "what is the difference between a view and a table materialization?",
    "how do I write a singular test?",
]
t = time.time()
r = Retriever()
print(f"chargement : {time.time() - t:.0f}s\n")
for q in QUESTIONS:
    print("=" * 90, "\nQ:", q)
    for mode in ("dense", "bm25", "hybrid_rerank"):
        t = time.time()
        hits = r.retrieve(q, k=3, mode=mode)
        print(f"  [{mode}] ({time.time() - t:.1f}s)")
        for h in hits:
            print(f"     - {h['url'].replace('https://docs.getdbt.com/', '')}")
    sys.stdout.flush()

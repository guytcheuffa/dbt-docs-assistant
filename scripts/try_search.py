"""Teste la recherche en ligne de commande.
Usage : python scripts/try_search.py "how do I make an incremental model?" [--mode dense|bm25|hybrid|hybrid_rerank]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse

from src.retrieval.search import Retriever

ap = argparse.ArgumentParser()
ap.add_argument("question")
ap.add_argument("--mode", default="hybrid_rerank")
ap.add_argument("-k", type=int, default=5)
args = ap.parse_args()

r = Retriever()
for i, h in enumerate(r.retrieve(args.question, k=args.k, mode=args.mode), 1):
    print(f"\n[{i}] score={h['score']:.3f} {h['title']} > {' > '.join(h['heading_path'])}\n    {h['url']}")
    print("    " + h["text"][:300].replace("\n", " ") + " ...")

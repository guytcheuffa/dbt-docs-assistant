"""Étape 3b : recherche hybride (vecteurs + BM25) avec fusion RRF et reranking.

Modes disponibles (utiles pour comparer à l'étape de mesures) :
  "dense"          vecteurs seuls
  "bm25"           recherche lexicale seule
  "hybrid"         fusion des deux (RRF)
  "hybrid_rerank"  fusion puis reranking par cross-encoder (défaut)
"""
import json
import re

import numpy as np
from fastembed import TextEmbedding
from fastembed.rerank.cross_encoder import TextCrossEncoder
from rank_bm25 import BM25Okapi

from src import config

TOKEN_RE = re.compile(r"[a-z0-9]+")
STOPWORDS = {"the", "a", "an", "of", "to", "in", "is", "are", "and", "or", "for", "on", "with",
             "how", "do", "i", "can", "what", "this", "that", "it", "be", "as", "by", "you", "your"}


def tokenize(text):
    """Découpe en mots en gardant les identifiants : is_incremental -> is_incremental, is, incremental."""
    out = []
    for w in re.findall(r"[A-Za-z0-9_]+", text.lower()):
        if w in STOPWORDS:
            continue
        out.append(w)
        if "_" in w:
            out.extend(p for p in w.split("_") if p and p not in STOPWORDS)
    return out


class Retriever:
    def __init__(self, rerank=True):
        with config.CHUNKS_PATH.open(encoding="utf-8") as f:
            self.chunks = [json.loads(line) for line in f]
        ids = json.loads((config.VECTORSTORE / "chunk_ids.json").read_text(encoding="utf-8"))
        assert ids == [c["chunk_id"] for c in self.chunks], "Index obsolète : relance build_index."
        self.emb = np.load(config.VECTORSTORE / "embeddings.npy")
        self.embedder = TextEmbedding(config.EMBEDDING_MODEL)
        self.bm25 = BM25Okapi([tokenize(c["title"] + " " + " ".join(c["heading_path"]) + " " + c["text"])
                               for c in self.chunks])
        self.reranker = TextCrossEncoder(config.RERANK_MODEL) if rerank else None

    # --- briques ---
    def dense(self, query, k):
        q = np.array(list(self.embedder.query_embed([query])), dtype=np.float32)[0]
        q /= np.linalg.norm(q)
        scores = self.emb @ q
        idx = np.argsort(-scores)[:k]
        return [(int(i), float(scores[i])) for i in idx]

    def lexical(self, query, k):
        scores = self.bm25.get_scores(tokenize(query))
        idx = np.argsort(-scores)[:k]
        return [(int(i), float(scores[i])) for i in idx if scores[i] > 0]

    @staticmethod
    def rrf(rankings, k=config.RRF_K):
        fused = {}
        for ranking in rankings:
            for rank, (i, _) in enumerate(ranking):
                fused[i] = fused.get(i, 0.0) + 1.0 / (k + rank + 1)
        return sorted(fused.items(), key=lambda x: -x[1])

    # --- point d'entrée ---
    def retrieve(self, query, k=5, mode="hybrid_rerank"):
        n = config.CANDIDATES_PER_RETRIEVER
        if mode == "dense":
            ranked = self.dense(query, k * 3)
        elif mode == "bm25":
            ranked = self.lexical(query, k * 3)
        else:
            ranked = self.rrf([self.dense(query, n), self.lexical(query, n)])
            if mode == "hybrid_rerank" and self.reranker is not None:
                cands = ranked[:config.RERANK_TOP]
                scores = list(self.reranker.rerank(query, [self.chunks[i]["text_for_embedding"] for i, _ in cands]))
                ranked = sorted(((i, float(s)) for (i, _), s in zip(cands, scores)), key=lambda x: -x[1])
        # un seul passage par section (url avec ancre) : évite les doublons dus au recouvrement
        seen, unique = set(), []
        for i, score in ranked:
            if self.chunks[i]["url"] not in seen:
                seen.add(self.chunks[i]["url"])
                unique.append((i, score))
        results = []
        for i, score in unique[:k]:
            c = self.chunks[i]
            results.append({"chunk_id": c["chunk_id"], "url": c["url"], "title": c["title"],
                            "heading_path": c["heading_path"], "text": c["text"], "score": score,
                            "also_at": c.get("also_at", [])})
        return results

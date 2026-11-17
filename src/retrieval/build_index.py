"""Étape 3a : calcule les embeddings de tous les passages.

- reprend là où il s'est arrêté (un fichier par tranche de PART_SIZE passages)
- assemble le résultat dans vectorstore/embeddings.npy
- vérifie l'ordre avec vectorstore/chunk_ids.json

Usage : python -m src.retrieval.build_index
        python -m src.retrieval.build_index --max-seconds 150   (pour s'arrêter proprement)
"""
import argparse
import json
import time

import numpy as np
from fastembed import TextEmbedding

from src import config


def load_chunks():
    with config.CHUNKS_PATH.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-seconds", type=float, default=None)
    args = ap.parse_args()

    start = time.time()
    chunks = load_chunks()
    parts_dir = config.VECTORSTORE / "parts"
    parts_dir.mkdir(parents=True, exist_ok=True)
    n_parts = (len(chunks) + config.PART_SIZE - 1) // config.PART_SIZE
    print(f"{len(chunks)} passages, {n_parts} tranches, modèle {config.EMBEDDING_MODEL}")

    model = TextEmbedding(config.EMBEDDING_MODEL)
    for p in range(n_parts):
        path = parts_dir / f"part_{p:03d}.npy"
        if path.exists():
            continue
        if args.max_seconds and time.time() - start > args.max_seconds:
            print(f"Arrêt propre (limite de temps). Relance la commande pour continuer ({p}/{n_parts} faites).")
            return
        lo, hi = p * config.PART_SIZE, min(len(chunks), (p + 1) * config.PART_SIZE)
        texts = [c["text_for_embedding"] for c in chunks[lo:hi]]
        vecs = np.array(list(model.embed(texts, batch_size=config.BATCH_SIZE)), dtype=np.float32)
        vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)   # normalisé : produit scalaire = cosinus
        np.save(path, vecs)
        print(f"tranche {p + 1}/{n_parts} ok ({time.time() - start:.0f}s)")

    emb = np.vstack([np.load(parts_dir / f"part_{p:03d}.npy") for p in range(n_parts)])
    assert emb.shape[0] == len(chunks), "nombre de vecteurs différent du nombre de passages"
    np.save(config.VECTORSTORE / "embeddings.npy", emb)
    (config.VECTORSTORE / "chunk_ids.json").write_text(
        json.dumps([c["chunk_id"] for c in chunks]), encoding="utf-8")
    print(f"Index terminé : {emb.shape} dans {config.VECTORSTORE}")


if __name__ == "__main__":
    main()

"""
Cosine-similarity search over stored precedent embeddings.

Pure numpy over JSON-stored vectors: no external vector database at
this scale. Search is always scoped to one profile and one request
type.
"""

import math

import numpy as np


def cosine_top_k(query_embedding, candidates, k=3, exclude_ids=()):
    """Return the k best (id, score) pairs.

    `candidates` is an iterable of (id, embedding list). Embeddings
    with a different length than the query are skipped. Invalid
    embeddings never raise: they score 0.
    """
    query = np.asarray(query_embedding, dtype=float)
    query_norm = np.linalg.norm(query)
    if not math.isfinite(query_norm) or query_norm == 0:
        return []
    unit_query = query / query_norm
    scored = []
    for cid, embedding in candidates:
        if cid in exclude_ids:
            continue
        try:
            vec = np.asarray(embedding, dtype=float)
        except (TypeError, ValueError):
            continue
        if vec.shape != query.shape:
            continue
        norm = np.linalg.norm(vec)
        if not math.isfinite(norm) or norm == 0:
            continue
        score = float(np.dot(unit_query, vec / norm))
        if math.isnan(score):
            continue
        scored.append((cid, score))
    scored.sort(key=lambda item: (-item[1], str(item[0])))
    return scored[:k]

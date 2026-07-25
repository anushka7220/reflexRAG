#!/usr/bin/env python3
# diagnose_retrieval.py
#
# Runs a query through the REAL retrieval + rerank path and prints where
# each candidate lands, so we can see exactly why a good chunk isn't
# reaching the answer. Run from backend/ with venv active:
#
#     python diagnose_retrieval.py "<pypdf repo_id>" "what does this repo do?"
#
# What it shows:
#   1. VECTOR stage: top-50 by cosine. Is the "# pypdf" intro chunk here?
#      At what rank? (If absent -> recall problem -> BM25 is the fix.)
#   2. RERANK stage: same chunks reranked. Did the intro get demoted?
#      Are any scores nan? (nan -> ranking corrupted -> fix that first.)

import sys
import math

from app.services.ingestion.embedding_service import embedding_service
from app.services.ingestion.vector_store import vector_store
from app.services.rag.reranker import reranker
import asyncio


def tag(text: str) -> str:
    """Flag the chunks we care about so they're easy to spot."""
    low = text.lower()
    if text.strip().startswith("# pypdf") or "pure-python pdf" in low or "free and open" in low:
        return " <<< INTRO (the answer)"
    if "contribution" in low or "contributions are welcome" in low:
        return " <-- contributing"
    if "changelog" in low or "developer experience" in low:
        return " <-- changelog"
    return ""


async def main(repo_id: str, query: str):
    print(f"\nQUERY: {query!r}\nREPO:  {repo_id}\n")

    # ---- Stage 1: vector search (exactly what retrieve() does) ----
    q_emb = await embedding_service.embed_single(query)
    results = vector_store.similarity_search(q_emb, repo_id=repo_id, top_k=50)
    print(f"=== VECTOR STAGE: {len(results)} candidates (top_k=50) ===")

    intro_rank = None
    for i, r in enumerate(results):
        head = r.chunk.content[:60].replace("\n", " ")
        mark = tag(r.chunk.content)
        if "INTRO" in mark and intro_rank is None:
            intro_rank = i + 1
        if i < 15 or mark:  # show top 15 + any flagged chunk lower down
            print(f"  {i+1:>2}. [{r.chunk.source_id[:24]:<24}] {head}{mark}")

    print()
    if intro_rank:
        print(f"  --> INTRO chunk is in vector results at rank {intro_rank}/50")
    else:
        print(f"  --> INTRO chunk NOT in vector top-50. This is a RECALL problem.")
        print(f"      The reranker never sees it. BM25 is the fix.")

    # ---- Stage 2: rerank (exactly what generate() does) ----
    reranked = await reranker.rerank(query, results)
    print(f"\n=== RERANK STAGE: top {len(reranked)} after cross-encoder ===")

    nan_count = 0
    intro_in_final = False
    for i, r in enumerate(reranked):
        score = getattr(r, "rerank_score", None)
        is_nan = score is not None and isinstance(score, float) and math.isnan(score)
        if is_nan:
            nan_count += 1
        head = r.chunk.content[:55].replace("\n", " ")
        mark = tag(r.chunk.content)
        if "INTRO" in mark:
            intro_in_final = True
        flag = " !!NAN!!" if is_nan else ""
        print(f"  {i+1}. score={score}{flag} [{r.chunk.source_id[:22]:<22}] {head}{mark}")

    print("\n=== VERDICT ===")
    if nan_count:
        print(f"  {nan_count} nan score(s) found. Ranking is CORRUPTED by nan sort keys.")
        print("  Fix the nan BEFORE anything else — it scrambles the order.")
    if intro_rank and not intro_in_final:
        print("  INTRO was retrieved by vector search but the RERANKER dropped it.")
        print("  -> reranker relevance problem. BM25 helps; query expansion helps more.")
    elif not intro_rank:
        print("  INTRO missing from candidates entirely -> pure RECALL problem -> BM25.")
    elif intro_in_final:
        print("  INTRO made it to the final set. If the answer was still bad,")
        print("  the problem is generation/prompt, not retrieval.")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print('usage: python diagnose_retrieval.py "<repo_id>" "<query>"')
        sys.exit(1)
    asyncio.run(main(sys.argv[1], sys.argv[2]))
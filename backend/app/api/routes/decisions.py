
# Decision archaeology endpoints.
# Returns structured decision nodes extracted during ingestion.
# These answer "why was this decision made" not "what does this code do".

from fastapi import APIRouter, HTTPException, Depends, Query
from app.core.dependencies import get_current_user
from app.core.supabase import supabase_admin, execute
from app.models.user import UserProfile
from app.models.decision import DecisionNodeResponse, RejectedAlternative, DecisionEvidenceItem
from app.services.ingestion.vector_store import vector_store
from app.services.ingestion.embedding_service import embedding_service

import structlog
from app.utils.timestamps import parse_pg_timestamp

log = structlog.get_logger(__name__)

router = APIRouter()


@router.get("/{repo_id}/decisions", response_model=list[DecisionNodeResponse])
async def list_decisions(
    repo_id: str,
    search: str = Query(None, description="Optional semantic search query"),
    limit: int = Query(20, le=100),
    offset: int = Query(0),
    current_user: UserProfile = Depends(get_current_user),
):
    """
    Returns decision nodes for a repo.

    Without a search query, returns the most recent decisions ordered
    by creation date. With a search query, does semantic similarity
    search against decision node embeddings to find relevant decisions.

    Example queries:
        "why did we choose JWT over sessions"
        "authentication architecture decisions"
        "database choice"
    """
    _assert_access(current_user.id, repo_id)

    if search:
        # Semantic search against decision node embeddings
        query_embedding = await embedding_service.embed_single(search)

        rows = execute(
            supabase_admin.rpc("match_decisions", {
                "query_embedding": query_embedding,
                "match_repo_id":   repo_id,
                "match_count":     limit,
            }).execute()
        )
    else:
        rows = execute(
            supabase_admin.table("decision_nodes")
            .select("*")
            .eq("repo_id", repo_id)
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )

    return [_row_to_response(r) for r in rows]


@router.get("/{repo_id}/decisions/{decision_id}", response_model=DecisionNodeResponse)
async def get_decision(
    repo_id: str,
    decision_id: str,
    current_user: UserProfile = Depends(get_current_user),
):
    """
    Returns a single decision node with its full source evidence.
    The evidence links back to the original PR or issue chunks
    so the user can read the raw discussion that produced this decision.
    """
    _assert_access(current_user.id, repo_id)

    rows = execute(
        supabase_admin.table("decision_nodes")
        .select("*")
        .eq("id", decision_id)
        .eq("repo_id", repo_id)
        .execute()
    )

    if not rows:
        raise HTTPException(status_code=404, detail="Decision not found")

    return _row_to_response(rows[0], fetch_evidence=True)


def _row_to_response(row: dict, fetch_evidence: bool = False) -> DecisionNodeResponse:
    """Converts a raw DB row into a DecisionNodeResponse."""
    alternatives = [
        RejectedAlternative(
            option=a.get("option", ""),
            reason=a.get("reason", ""),
        )
        for a in (row.get("alternatives_rejected") or [])
    ]

    evidence = []
    if fetch_evidence and row.get("source_chunk_ids"):
        chunks = vector_store.get_chunks_by_ids(row["source_chunk_ids"])
        evidence = [
            DecisionEvidenceItem(
                chunk_id=c.id,
                source_type=c.source_type,
                source_id=c.source_id,
                url=c.url,
                excerpt=c.content[:200],
            )
            for c in chunks
        ]

    from datetime import datetime
    return DecisionNodeResponse(
        id=row["id"],
        decision=row["decision"],
        alternatives_rejected=alternatives,
        reasoning=row.get("reasoning", ""),
        evidence=evidence,
        created_at=parse_pg_timestamp(row["created_at"]),
    )


def _assert_access(user_id: str, repo_id: str) -> None:
    links = execute(
        supabase_admin.table("user_repos")
        .select("repo_id")
        .eq("user_id", user_id)
        .eq("repo_id", repo_id)
        .execute()
    )
    if not links:
        raise HTTPException(status_code=403, detail="You do not have access to this repo.")

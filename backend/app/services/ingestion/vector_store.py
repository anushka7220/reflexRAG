# vector_store.py
#
# Reads and writes the chunks table in Supabase with pgvector.
# Two responsibilities only: upsert chunks, search by similarity.
#
# THE CORE SQL:
#   SELECT *, 1 - (embedding <=> query_vector) AS score
#   FROM chunks
#   WHERE repo_id = $repo_id
#   ORDER BY score DESC
#   LIMIT 50
#
# The <=> operator is pgvector's cosine distance (0 = identical, 2 = opposite).
# We subtract from 1 to convert to similarity (1 = identical, -1 = opposite).
# We filter by repo_id so users only retrieve chunks from their selected repo.
#
# DEDUPLICATION:
# Every chunk has a content_hash (SHA-256 of its text).
# Before inserting, we check if that hash exists.
# If yes, skip. The chunk is already in the DB from a previous ingestion.
# This is what makes the shared chunk store work.

import structlog
from dataclasses import asdict
from datetime import datetime

from app.core.supabase import supabase_admin, execute
from app.models.chunk import Chunk, ChunkResult
from app.utils.timestamps import parse_pg_timestamp

log = structlog.get_logger(__name__)


class VectorStore:
    """
    Handles all reads and writes to the chunks table.

    Usage:
        store = VectorStore()
        await store.upsert_chunks(chunks)
        results = await store.similarity_search(query_vector, repo_id, top_k=50)
    """

    def upsert_chunks(self, chunks: list[Chunk]) -> tuple[int, int]:
        """
        Inserts chunks into pgvector, skipping any that already exist.

        The dedup check uses content_hash. If a hash is already in the DB,
        the chunk came from a previous ingestion of the same repo by any user.
        We skip it to avoid duplicate embeddings for identical content.

        Args:
            chunks: List of Chunk objects with embeddings already filled.

        Returns:
            Tuple of (inserted_count, skipped_count).

        Note:
            This is synchronous because Supabase-py is synchronous.
            Call from a Celery task, not from an async FastAPI endpoint directly.
        """
        if not chunks:
            return 0, 0

        inserted = 0
        skipped  = 0

        # Batch the hash check to avoid N+1 queries.
        # One query to find all existing hashes, then check locally.
        all_hashes  = [c.content_hash for c in chunks]
        existing    = self._get_existing_hashes(all_hashes)

        rows_to_insert = []
        for chunk in chunks:
            if chunk.content_hash in existing:
                skipped += 1
                continue

            if not chunk.embedding:
                log.warning("chunk_missing_embedding", source_id=chunk.source_id)
                skipped += 1
                continue

            rows_to_insert.append(self._chunk_to_row(chunk))

        if rows_to_insert:
            # Insert in batches of 100 to avoid request size limits
            for i in range(0, len(rows_to_insert), 100):
                batch = rows_to_insert[i : i + 100]
                try:
                    response = supabase_admin.table("chunks").insert(batch).execute()
                    execute(response)
                    inserted += len(batch)
                    log.info("chunks_inserted", batch=len(batch))
                except Exception as e:
                    log.error("chunk_insert_failed", error=str(e), batch_size=len(batch))
                    raise

        log.info(
            "upsert_complete",
            total=len(chunks),
            inserted=inserted,
            skipped=skipped,
        )
        return inserted, skipped

    def similarity_search(
        self,
        query_embedding: list[float],
        repo_id: str,
        top_k: int = 50,
    ) -> list[ChunkResult]:
        """
        Finds the top_k chunks most similar to the query embedding.

        Uses pgvector's cosine distance operator <=> via Supabase RPC.
        We call a Postgres function instead of raw SQL because Supabase-py
        does not support the <=> operator directly in its query builder.

        Args:
            query_embedding: 1024-dim float vector from EmbeddingService.embed_single().
            repo_id:         Scopes the search to one repo's chunks.
            top_k:           Number of results to return (50 before reranking).

        Returns:
            List of ChunkResult objects sorted by cosine similarity descending.
        """
        try:
            response = supabase_admin.rpc(
                "match_chunks",
                {
                    "query_embedding": query_embedding,
                    "match_repo_id":   repo_id,
                    "match_count":     top_k,
                },
            ).execute()

            rows = execute(response)

        except Exception as e:
            log.error("similarity_search_failed", repo_id=repo_id, error=str(e))
            return []

        results = []
        for row in rows:
            chunk = self._row_to_chunk(row)
            results.append(ChunkResult(
                chunk=chunk,
                score=float(row.get("similarity", 0.0)),
                rerank_score=None,
            ))

        log.info(
            "similarity_search_done",
            repo_id=repo_id,
            top_k=top_k,
            returned=len(results),
        )
        return results

    def get_chunks_by_ids(self, chunk_ids: list[str]) -> list[Chunk]:
        """
        Fetches specific chunks by their UUIDs.
        Used by the decision extractor to retrieve source evidence for citations.

        Args:
            chunk_ids: List of chunk UUID strings.

        Returns:
            List of Chunk objects in no guaranteed order.
        """
        if not chunk_ids:
            return []

        try:
            response = (
                supabase_admin
                .table("chunks")
                .select("*")
                .in_("id", chunk_ids)
                .execute()
            )
            rows = execute(response)
            return [self._row_to_chunk(row) for row in rows]
        except Exception as e:
            log.error("get_chunks_by_ids_failed", error=str(e))
            return []

    def get_chunk_count(self, repo_id: str) -> int:
        """Returns total number of chunks stored for a repo."""
        try:
            response = (
                supabase_admin
                .table("chunks")
                .select("id", count="exact")
                .eq("repo_id", repo_id)
                .execute()
            )
            return response.count or 0
        except Exception as e:
            log.error("chunk_count_failed", repo_id=repo_id, error=str(e))
            return 0

    def delete_chunks_for_repo(self, repo_id: str) -> int:
        """
        Deletes all chunks for a repo.
        Called when a user deletes a repo from their dashboard.
        Only deletes if no other user has that repo linked.

        Args:
            repo_id: UUID of the repo.

        Returns:
            Number of chunks deleted.
        """
        try:
            count    = self.get_chunk_count(repo_id)
            response = (
                supabase_admin
                .table("chunks")
                .delete()
                .eq("repo_id", repo_id)
                .execute()
            )
            execute(response)
            log.info("chunks_deleted", repo_id=repo_id, count=count)
            return count
        except Exception as e:
            log.error("chunk_delete_failed", repo_id=repo_id, error=str(e))
            return 0

    def _get_existing_hashes(
        self,
        hashes: list[str],
        batch_size: int = 100,
    ) -> set[str]:
        """
        Batch-fetches content hashes that already exist in the DB.

        Supabase/PostgREST can struggle with very large IN() lists,
        so split them into smaller batches and merge the results.
        """
        existing: set[str] = set()

        try:
            for i in range(0, len(hashes), batch_size):
                batch = hashes[i:i + batch_size]

                response = (
                    supabase_admin
                    .table("chunks")
                    .select("content_hash")
                    .in_("content_hash", batch)
                    .execute()
                )

                rows = execute(response)
                existing.update(row["content_hash"] for row in rows)

            return existing

        except Exception as e:
            log.error(
                "hash_check_failed",
                error=str(e),
                total_hashes=len(hashes),
            )
            return set()

    def _chunk_to_row(self, chunk: Chunk) -> dict:
        """Converts a Chunk dataclass to a dict for Supabase insert."""
        return {
            "repo_id":           chunk.repo_id,
            "content":           chunk.content,
            "embedding":         chunk.embedding,
            "source_type":       chunk.source_type,
            "source_id":         chunk.source_id,
            "status":            chunk.status,
            "version_tag":       chunk.version_tag,
            "content_hash":      chunk.content_hash,
            "source_created_at": chunk.source_created_at.isoformat(),
            "url":               chunk.url,
            "file_path":         chunk.file_path,
            "language":          chunk.language,
            "start_line":        chunk.start_line,
            "end_line":          chunk.end_line,
            "files_touched":     chunk.files_touched or [],
        }

    def _row_to_chunk(self, row: dict) -> Chunk:
        """
        Converts a raw Supabase row dict back into a Chunk dataclass.

        Supabase's REST layer sometimes serializes the pgvector embedding
        column as a JSON string rather than a native array, depending on
        the query path. Downstream cosine similarity does elementwise
        float multiplication, which crashes with "can't multiply sequence
        by non-int of type str" if this is left as a string. Parse defensively.
        """
        embedding = row.get("embedding", [])
        if isinstance(embedding, str):
            import json
            try:
                embedding = json.loads(embedding)
            except (json.JSONDecodeError, TypeError):
                embedding = []

        return Chunk(
            id=row.get("id", ""),
            repo_id=row["repo_id"],
            content=row["content"],
            embedding=embedding,
            source_type=row["source_type"],
            source_id=row["source_id"],
            status=row.get("status", "none"),
            version_tag=row.get("version_tag"),
            content_hash=row["content_hash"],
            source_created_at=parse_pg_timestamp(row["source_created_at"]),
            url=row.get("url", ""),
            file_path=row.get("file_path"),
            language=row.get("language"),
            start_line=row.get("start_line"),
            end_line=row.get("end_line"),
            files_touched=row.get("files_touched") or [],
        )


vector_store = VectorStore()
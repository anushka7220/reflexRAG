# hashing.py
#
# Content hash utilities used for chunk deduplication.
# The sha256 hash of a chunk's text is the deduplication key in pgvector.
# If a hash already exists, the chunk is skipped — no re-embedding needed.

import hashlib


def sha256(text: str) -> str:
    """
    Returns the SHA-256 hex digest of a string.
    Used by the Chunker to compute content_hash for every chunk.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

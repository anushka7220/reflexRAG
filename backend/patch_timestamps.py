#!/usr/bin/env python3
"""
Patches every datetime.fromisoformat() call on Supabase values to use the
version-safe parse_pg_timestamp() helper instead.

Run from the backend/ directory:
    python3 patch_timestamps.py

Safe to run twice: it detects already-patched files and skips them.
"""
import re
import sys
import os

TARGETS = [
    "app/services/ingestion/vector_store.py",
    "app/services/ingestion/orchestrator.py",
    "app/api/routes/decisions.py",
]

IMPORT_LINE = "from app.utils.timestamps import parse_pg_timestamp"

# Matches both the multi-line and single-line forms of:
#   datetime.fromisoformat(  row["x"].replace("Z", "+00:00")  )
CALL = re.compile(
    r'datetime\.fromisoformat\(\s*'
    r'(row\[[\'"][\w_]+[\'"]\])'
    r'\.replace\(\s*[\'"]Z[\'"]\s*,\s*[\'"]\+00:00[\'"]\s*\)\s*\)',
    re.MULTILINE,
)

def patch(path: str) -> str:
    if not os.path.exists(path):
        return f"SKIP (not found): {path}"

    src = open(path).read()
    original = src

    n = len(CALL.findall(src))
    if n == 0 and IMPORT_LINE in src:
        return f"OK   (already patched): {path}"
    if n == 0:
        return f"WARN (no fromisoformat calls found): {path}"

    # Replace the calls
    src = CALL.sub(r'parse_pg_timestamp(\1)', src)

    # Add the import after the last existing 'from app.' import, or after
    # the last top-level import if none exist.
    if IMPORT_LINE not in src:
        lines = src.split("\n")
        insert_at = None
        for i, line in enumerate(lines):
            if line.startswith("from app.") or line.startswith("import "):
                insert_at = i
        if insert_at is None:
            return f"FAIL (no import anchor found): {path}"
        lines.insert(insert_at + 1, IMPORT_LINE)
        src = "\n".join(lines)

    if src == original:
        return f"WARN (nothing changed): {path}"

    # Verify it still parses before writing
    import ast
    try:
        ast.parse(src)
    except SyntaxError as e:
        return f"FAIL (patch would break syntax, not written): {path} -> {e}"

    open(path, "w").write(src)
    return f"OK   (patched {n} call{'s' if n != 1 else ''}): {path}"


if __name__ == "__main__":
    if not os.path.exists("app"):
        print("ERROR: run this from the backend/ directory (no app/ folder here)")
        sys.exit(1)
    print("Patching timestamp parsing...\n")
    for t in TARGETS:
        print("  " + patch(t))
    print("\nDone. Restart uvicorn and celery to pick up the changes.")
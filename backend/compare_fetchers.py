#!/usr/bin/env python3
# compare_fetchers.py
#
# Runs the REST fetcher and the GraphQL fetcher against the SAME repository
# and reports whether they produce equivalent data, plus how long and how
# many requests each took. Run this BEFORE switching the orchestrator to
# GraphQL, so the switch is based on evidence rather than hope.
#
# Usage (from backend/, venv active):
#     python compare_fetchers.py sindresorhus/slugify
#
# What "equivalent" means here, honestly:
#   - Same issue/PR NUMBERS retrieved (the set, not the order)
#   - Same comment counts per item, within the shared caps
#   - Same files_changed per PR (the join key — this one must match exactly)
# Timestamps and body whitespace can differ trivially between APIs; those
# are reported but not treated as failures.

import asyncio
import sys
import time

from app.core.config import settings
from app.services.ingestion.github_fetcher import GitHubFetcher
from app.services.ingestion.github_fetcher_graphql import GitHubFetcherGraphQL


def banner(text):
    print(f"\n{'=' * 60}\n{text}\n{'=' * 60}")


async def run(owner: str, name: str):
    token = settings.GITHUB_PERSONAL_ACCESS_TOKEN or None
    if not token:
        print("ERROR: GITHUB_PERSONAL_ACCESS_TOKEN is required (GraphQL has no anonymous tier)")
        sys.exit(1)

    rest = GitHubFetcher(github_token=token)
    gql = GitHubFetcherGraphQL(github_token=token)

    banner(f"REST fetch: {owner}/{name}")
    t0 = time.time()
    rest_issues = await rest.fetch_issues(owner, name)
    rest_prs = await rest.fetch_prs(owner, name)
    rest_time = time.time() - t0
    print(f"issues={len(rest_issues)}  prs={len(rest_prs)}  time={rest_time:.1f}s")

    banner(f"GraphQL fetch: {owner}/{name}")
    t0 = time.time()
    gql_issues = await gql.fetch_issues(owner, name)
    gql_prs = await gql.fetch_prs(owner, name)
    gql_time = time.time() - t0
    print(f"issues={len(gql_issues)}  prs={len(gql_prs)}  time={gql_time:.1f}s")

    banner("COMPARISON")
    problems = 0

    # 1. Same items retrieved?
    ri = {i.number for i in rest_issues}
    gi = {i.number for i in gql_issues}
    if ri == gi:
        print(f"[ok] issue sets match ({len(ri)} issues)")
    else:
        problems += 1
        print(f"[DIFF] issues only in REST: {sorted(ri - gi)}")
        print(f"[DIFF] issues only in GraphQL: {sorted(gi - ri)}")
        print("       (ordering/caps can cause tail differences; small diffs at")
        print("        the cap boundary are expected, large diffs are not)")

    rp = {p.number for p in rest_prs}
    gp = {p.number for p in gql_prs}
    if rp == gp:
        print(f"[ok] PR sets match ({len(rp)} prs)")
    else:
        problems += 1
        print(f"[DIFF] prs only in REST: {sorted(rp - gp)}")
        print(f"[DIFF] prs only in GraphQL: {sorted(gp - rp)}")

    # 2. THE JOIN KEY: files_changed must match per PR. This is the field
    #    the code-to-discussion join depends on; a mismatch here silently
    #    degrades the product's core feature.
    gql_by_num = {p.number: p for p in gql_prs}
    join_ok = True
    for p in rest_prs:
        g = gql_by_num.get(p.number)
        if g is None:
            continue
        if set(p.files_changed) != set(g.files_changed):
            join_ok = False
            problems += 1
            print(f"[DIFF] PR #{p.number} files_changed:")
            print(f"       REST only:    {sorted(set(p.files_changed) - set(g.files_changed))}")
            print(f"       GraphQL only: {sorted(set(g.files_changed) - set(p.files_changed))}")
    if join_ok:
        print("[ok] files_changed (join key) matches on every shared PR")

    # 3. Comment coverage per item (counts, not verbatim text: the two APIs
    #    can order comments differently and whitespace can differ).
    gql_issue_by_num = {i.number: i for i in gql_issues}
    worst = 0
    for i in rest_issues:
        g = gql_issue_by_num.get(i.number)
        if g is None:
            continue
        delta = abs(len(i.comments) - len(g.comments))
        worst = max(worst, delta)
    print(f"[{'ok' if worst <= 1 else 'DIFF'}] max comment-count delta on shared issues: {worst}")
    if worst > 1:
        problems += 1

    banner("VERDICT")
    speedup = rest_time / gql_time if gql_time > 0 else float("inf")
    print(f"REST:    {rest_time:.1f}s")
    print(f"GraphQL: {gql_time:.1f}s   ({speedup:.1f}x faster)")
    if problems == 0:
        print("\nEQUIVALENT. Safe to switch the orchestrator to GraphQL for")
        print("issues/PRs (commits and tarball stay on REST by design).")
    else:
        print(f"\n{problems} difference(s) found. Review above before switching.")
        print("Small tail differences at the cap boundary are usually benign;")
        print("join-key (files_changed) differences are NOT.")


if __name__ == "__main__":
    if len(sys.argv) != 2 or "/" not in sys.argv[1]:
        print("usage: python compare_fetchers.py owner/repo")
        sys.exit(1)
    owner, name = sys.argv[1].split("/", 1)
    asyncio.run(run(owner, name))
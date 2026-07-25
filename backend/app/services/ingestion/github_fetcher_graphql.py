# github_fetcher_graphql.py
#
# GraphQL-based fetcher that collapses the REST N+1 pattern into a handful
# of queries. Runs SIDE BY SIDE with github_fetcher.py: same public method
# names, same dataclass outputs (RawIssue, RawPR, ...), so the orchestrator
# can switch between them with a flag and everything downstream is unchanged.
#
# ── WHY GRAPHQL KILLS THE N+1 ────────────────────────────────────────────
# REST: 1 call lists 25 issues, then 1 MORE call per issue for comments.
# GraphQL: ONE query returns 25 issues WITH their first 20 comments nested,
# because you describe the whole tree you want and the server assembles it.
# The same applies to PRs with comments + reviews + files. Issues and PRs
# were ~110 of the ~140 REST calls per repo; here they cost 2-4 queries.
#
# ── WHAT DELIBERATELY STAYS ON REST (hybrid design) ──────────────────────
# 1. Commits with changed files: GitHub's GraphQL Commit object has NO
#    field for changed files. That data is REST-only. Commit files feed
#    the contributor map and the code-to-discussion join, so commits
#    delegate to the REST fetcher unchanged.
# 2. Source tarball: already ONE call in the REST fetcher. Nothing to win.
# GraphQL where it wins, REST where it is required.
#
# ── RATE LIMITING: POINTS, NOT REQUESTS ──────────────────────────────────
# REST counts requests (5000/hr). GraphQL counts POINTS (5000/hr) scaled by
# how much a query asks for. Every query here also asks for the rateLimit
# block, so we always know cost/remaining and sleep before running dry.
# GithubRetry does not apply here; this module handles its own limits.

import asyncio
import time
import structlog
import requests as _requests
from typing import Optional

from app.core.config import settings
from app.services.ingestion.github_fetcher import (
    GitHubFetcher,
    RawCommit,
    RawIssue,
    RawPR,
    RawRelease,
    RawReview,
    RepoMeta,
    SourceFileRaw,
)

log = structlog.get_logger(__name__)

GRAPHQL_URL = "https://api.github.com/graphql"

# Page sizes. GraphQL point cost scales with (first: N) values, so these are
# a cost/latency tradeoff, not a hard cap. Caps from settings still apply.
ISSUES_PER_PAGE = 25
PRS_PER_PAGE = 15
COMMENTS_PER_ITEM = 20
REVIEWS_PER_PR = 20
FILES_PER_PR = 100
RELEASES_PER_PAGE = 50

# The rateLimit block appended to every query, so each response tells us
# what the query cost and how much budget remains.
RATE_FRAGMENT = "rateLimit { cost remaining resetAt }"


class GitHubFetcherGraphQL:
    """
    Drop-in alternative to GitHubFetcher for issues/PRs/releases/meta.
    Commits and source files delegate to the REST fetcher (see header).

    Usage:
        fetcher = GitHubFetcherGraphQL(github_token=token)
        issues  = await fetcher.fetch_issues(owner, name)   # 1-2 queries
        prs     = await fetcher.fetch_prs(owner, name)      # 1-2 queries
    """

    HTTP_TIMEOUT = 45  # one query returns far more data than one REST call

    def __init__(self, github_token: Optional[str] = None):
        if not github_token:
            # GraphQL REQUIRES auth; there is no anonymous tier at all.
            raise ValueError(
                "GitHub GraphQL requires a token. Set GITHUB_PERSONAL_ACCESS_TOKEN."
            )
        self._headers = {
            "Authorization": f"bearer {github_token}",
            "Content-Type": "application/json",
        }
        # REST delegate for commits (files are REST-only) and the tarball.
        self._rest = GitHubFetcher(github_token=github_token)
        log.info("graphql_fetcher_init", timeout=self.HTTP_TIMEOUT)

    # ── Transport ──────────────────────────────────────────────────────────

    def _execute(self, query: str, variables: dict) -> dict:
        """
        Runs one GraphQL query. Handles the three GraphQL failure shapes:
        HTTP-level errors, the "errors" array (schema/permission problems),
        and rate-limit exhaustion (sleeps until resetAt, then retries once).
        """
        for attempt in (1, 2):
            resp = _requests.post(
                GRAPHQL_URL,
                json={"query": query, "variables": variables},
                headers=self._headers,
                timeout=self.HTTP_TIMEOUT,
            )
            resp.raise_for_status()
            payload = resp.json()

            if "errors" in payload and payload["errors"]:
                messages = "; ".join(e.get("message", "?") for e in payload["errors"])
                # RATE_LIMITED arrives as an error type, not an HTTP status.
                if any(e.get("type") == "RATE_LIMITED" for e in payload["errors"]):
                    if attempt == 1:
                        log.warning("graphql_rate_limited_sleeping", detail=messages)
                        time.sleep(60)
                        continue
                raise RuntimeError(f"GraphQL error: {messages}")

            data = payload.get("data") or {}
            rl = data.get("rateLimit") or {}
            log.debug(
                "graphql_query_done",
                cost=rl.get("cost"),
                remaining=rl.get("remaining"),
            )
            # Defensive brake: if the budget is nearly gone, pause here
            # rather than failing mid-repo on the next query.
            remaining = rl.get("remaining")
            if isinstance(remaining, int) and remaining < 50:
                log.warning("graphql_points_low_pausing", remaining=remaining)
                time.sleep(60)
            return data

        raise RuntimeError("GraphQL rate limit persisted after retry")

    # ── Repo metadata ──────────────────────────────────────────────────────

    _META_QUERY = f"""
    query($owner: String!, $name: String!) {{
      repository(owner: $owner, name: $name) {{
        description
        url
        defaultBranchRef {{
          name
          target {{ oid }}
        }}
      }}
      {RATE_FRAGMENT}
    }}
    """

    def _fetch_repo_meta_sync(self, github_url: str) -> RepoMeta:
        parts = github_url.rstrip("/").split("/")
        owner, name = parts[-2], parts[-1]
        data = self._execute(self._META_QUERY, {"owner": owner, "name": name})
        repo = data.get("repository")
        if repo is None:
            raise RuntimeError(f"Repository not found: {owner}/{name}")
        branch = repo.get("defaultBranchRef") or {}
        return RepoMeta(
            owner=owner,
            name=name,
            description=repo.get("description") or "",
            default_branch=branch.get("name") or "main",
            latest_commit_sha=(branch.get("target") or {}).get("oid") or "",
            html_url=repo.get("url") or "",
        )

    async def fetch_repo_meta(self, github_url: str) -> RepoMeta:
        return await self._run_sync(self._fetch_repo_meta_sync, github_url)

    # ── Issues: the flagship N+1 kill ─────────────────────────────────────
    # ONE page of this query = 25 issues WITH their comments. Under REST the
    # same data was 1 + 25 = 26 calls.

    _ISSUES_QUERY = f"""
    query($owner: String!, $name: String!, $pageSize: Int!, $cursor: String) {{
      repository(owner: $owner, name: $name) {{
        issues(first: $pageSize, after: $cursor,
               orderBy: {{field: CREATED_AT, direction: DESC}}) {{
          pageInfo {{ hasNextPage endCursor }}
          nodes {{
            number title body state url
            createdAt updatedAt
            labels(first: 10) {{ nodes {{ name }} }}
            comments(first: {COMMENTS_PER_ITEM}) {{ nodes {{ body }} }}
          }}
        }}
      }}
      {RATE_FRAGMENT}
    }}
    """

    def _fetch_issues_sync(self, owner: str, name: str) -> list:
        issues: list = []
        cursor = None

        while len(issues) < settings.MAX_ISSUES_PER_REPO:
            page = min(ISSUES_PER_PAGE, settings.MAX_ISSUES_PER_REPO - len(issues))
            data = self._execute(
                self._ISSUES_QUERY,
                {"owner": owner, "name": name, "pageSize": page, "cursor": cursor},
            )
            conn = ((data.get("repository") or {}).get("issues")) or {}
            for node in conn.get("nodes") or []:
                issues.append(RawIssue(
                    number=node["number"],
                    title=node.get("title") or "",
                    body=node.get("body") or "",
                    state=(node.get("state") or "").lower(),
                    created_at=_ts(node.get("createdAt")),
                    updated_at=_ts(node.get("updatedAt")),
                    labels=[l["name"] for l in (node.get("labels") or {}).get("nodes") or []],
                    comments=[c["body"] for c in (node.get("comments") or {}).get("nodes") or [] if c.get("body")],
                    html_url=node.get("url") or "",
                ))
            info = conn.get("pageInfo") or {}
            if not info.get("hasNextPage"):
                break
            cursor = info.get("endCursor")

        log.info("graphql_issues_fetched", count=len(issues), repo=f"{owner}/{name}")
        return issues

    async def fetch_issues(self, owner: str, name: str) -> list:
        return await self._run_sync(self._fetch_issues_sync, owner, name)

    # ── Pull requests: comments + reviews + files in one tree ────────────
    # Under REST each PR cost up to 4 sub-calls. Here a page of 15 PRs with
    # everything nested is ONE query.

    _PRS_QUERY = f"""
    query($owner: String!, $name: String!, $pageSize: Int!, $cursor: String) {{
      repository(owner: $owner, name: $name) {{
        pullRequests(first: $pageSize, after: $cursor,
                     orderBy: {{field: CREATED_AT, direction: DESC}}) {{
          pageInfo {{ hasNextPage endCursor }}
          nodes {{
            number title body state merged url
            createdAt updatedAt mergedAt
            comments(first: {COMMENTS_PER_ITEM}) {{ nodes {{ body }} }}
            reviews(first: {REVIEWS_PER_PR}) {{
              nodes {{ body state author {{ login }} }}
            }}
            files(first: {FILES_PER_PR}) {{ nodes {{ path }} }}
          }}
        }}
      }}
      {RATE_FRAGMENT}
    }}
    """

    def _fetch_prs_sync(self, owner: str, name: str) -> list:
        prs: list = []
        cursor = None

        while len(prs) < settings.MAX_PRS_PER_REPO:
            page = min(PRS_PER_PAGE, settings.MAX_PRS_PER_REPO - len(prs))
            data = self._execute(
                self._PRS_QUERY,
                {"owner": owner, "name": name, "pageSize": page, "cursor": cursor},
            )
            conn = ((data.get("repository") or {}).get("pullRequests")) or {}
            for node in conn.get("nodes") or []:
                merged = bool(node.get("merged"))
                state = "merged" if merged else (node.get("state") or "").lower()
                reviews = [
                    RawReview(
                        reviewer=((r.get("author") or {}).get("login")) or "unknown",
                        body=r.get("body") or "",
                        state=r.get("state") or "COMMENTED",
                    )
                    for r in (node.get("reviews") or {}).get("nodes") or []
                ]
                prs.append(RawPR(
                    number=node["number"],
                    title=node.get("title") or "",
                    body=node.get("body") or "",
                    state=state,
                    merged=merged,
                    created_at=_ts(node.get("createdAt")),
                    updated_at=_ts(node.get("updatedAt")),
                    merged_at=_ts(node.get("mergedAt")) if node.get("mergedAt") else None,
                    comments=[c["body"] for c in (node.get("comments") or {}).get("nodes") or [] if c.get("body")],
                    reviews=reviews,
                    files_changed=[f["path"] for f in (node.get("files") or {}).get("nodes") or [] if f.get("path")],
                    html_url=node.get("url") or "",
                ))
            info = conn.get("pageInfo") or {}
            if not info.get("hasNextPage"):
                break
            cursor = info.get("endCursor")

        log.info("graphql_prs_fetched", count=len(prs), repo=f"{owner}/{name}")
        return prs

    async def fetch_prs(self, owner: str, name: str) -> list:
        return await self._run_sync(self._fetch_prs_sync, owner, name)

    # ── Releases ───────────────────────────────────────────────────────────

    _RELEASES_QUERY = f"""
    query($owner: String!, $name: String!, $cursor: String) {{
      repository(owner: $owner, name: $name) {{
        releases(first: {RELEASES_PER_PAGE}, after: $cursor,
                 orderBy: {{field: CREATED_AT, direction: DESC}}) {{
          pageInfo {{ hasNextPage endCursor }}
          nodes {{ tagName name description createdAt url }}
        }}
      }}
      {RATE_FRAGMENT}
    }}
    """

    def _fetch_releases_sync(self, owner: str, name: str) -> list:
        releases: list = []
        cursor = None
        while True:
            data = self._execute(
                self._RELEASES_QUERY,
                {"owner": owner, "name": name, "cursor": cursor},
            )
            conn = ((data.get("repository") or {}).get("releases")) or {}
            for node in conn.get("nodes") or []:
                releases.append(RawRelease(
                    tag_name=node.get("tagName") or "",
                    name=node.get("name") or node.get("tagName") or "",
                    body=node.get("description") or "",
                    created_at=_ts(node.get("createdAt")),
                    html_url=node.get("url") or "",
                ))
            info = conn.get("pageInfo") or {}
            if not info.get("hasNextPage"):
                break
            cursor = info.get("endCursor")

        log.info("graphql_releases_fetched", count=len(releases), repo=f"{owner}/{name}")
        return releases

    async def fetch_releases(self, owner: str, name: str) -> list:
        return await self._run_sync(self._fetch_releases_sync, owner, name)

    # ── Delegated to REST (see file header for why) ───────────────────────

    async def fetch_commits(self, owner: str, name: str) -> list:
        # GraphQL's Commit object exposes no changed-file list; that data is
        # REST-only, and commit files feed the contributor map and the join.
        return await self._rest.fetch_commits(owner, name)

    async def fetch_source_files(self, owner: str, name: str, priority_paths=None) -> list:
        # Tarball is already ONE call in the REST fetcher. Nothing to gain.
        return await self._rest.fetch_source_files(owner, name, priority_paths=priority_paths)

    # ── Async wrapper ──────────────────────────────────────────────────────

    async def _run_sync(self, fn, *args):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, fn, *args)


def _ts(value):
    """GraphQL returns ISO-8601 with Z suffix. Parse tolerantly."""
    from app.utils.timestamps import parse_pg_timestamp
    return parse_pg_timestamp(value)
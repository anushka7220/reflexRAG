# api/routes/webhooks.py
#
# GitHub webhook handler for differential re-ingestion.
#
# WHAT WEBHOOKS DO:
# When a repo changes on GitHub (new issue, merged PR, new commit),
# GitHub sends a POST request to this endpoint with the event payload.
# We validate the signature, extract what changed, and queue a
# differential ingestion so the repo stays current without re-indexing
# everything from scratch.
#
# SETUP:
# In your GitHub OAuth App or on the specific repo settings page,
# register: https://your-backend.onrender.com/webhooks/github
# with content type: application/json
# and the secret matching GITHUB_WEBHOOK_SECRET in your .env

from fastapi import APIRouter, Request, HTTPException, status
from app.core.security import verify_github_webhook
from app.core.supabase import supabase_admin, execute
from celery_worker.tasks import differential_ingest

import structlog

log = structlog.get_logger(__name__)

router = APIRouter()


@router.post("/github")
async def github_webhook(request: Request):
    """
    Receives GitHub webhook events and queues differential re-ingestion.

    Validates the X-Hub-Signature-256 header to confirm the request
    genuinely came from GitHub and not from an attacker trying to
    trigger re-ingestion with fake data.

    Handles these event types:
        push:           new commits pushed, re-index changed files
        issues:         issue opened, closed, edited
        pull_request:   PR opened, merged, closed
        issue_comment:  new comment on issue or PR

    All other event types are acknowledged but ignored.
    """
    # Read the raw body before any parsing.
    # Signature validation must happen on the exact bytes GitHub sent.
    body = await request.body()

    signature = request.headers.get("X-Hub-Signature-256", "")
    if not verify_github_webhook(body, signature):
        log.warning("webhook_signature_invalid", signature=signature[:20])
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid webhook signature.",
        )

    event_type = request.headers.get("X-GitHub-Event", "")
    payload = await request.json()

    log.info("webhook_received", event_type=event_type)

    # Only process events that change content we have indexed
    if event_type not in ("push", "issues", "pull_request", "issue_comment"):
        return {"received": True, "action": "ignored", "event": event_type}

    # Extract repo info from payload
    repo_info = payload.get("repository", {})
    github_url = repo_info.get("html_url", "")

    if not github_url:
        return {"received": True, "action": "ignored", "reason": "no repo url in payload"}

    # Find this repo in our database
    rows = execute(
        supabase_admin.table("repos")
        .select("id, latest_commit_sha, status")
        .eq("github_url", github_url)
        .execute()
    )

    if not rows:
        # Repo not ingested by any user — nothing to update
        return {"received": True, "action": "ignored", "reason": "repo not indexed"}

    repo = rows[0]

    if repo["status"] not in ("done",):
        # Repo is still being ingested or failed — skip
        return {"received": True, "action": "ignored", "reason": f"repo status is {repo['status']}"}

    # For push events, use the before SHA as the differential baseline.
    # For issue/PR events, use the stored latest commit SHA.
    if event_type == "push":
        since_sha = payload.get("before", repo["latest_commit_sha"])
    else:
        since_sha = repo["latest_commit_sha"]

    if not since_sha:
        return {"received": True, "action": "ignored", "reason": "no baseline SHA available"}

    # Queue differential ingestion
    differential_ingest.delay(repo_id=repo["id"], since_sha=since_sha)

    log.info(
        "differential_ingest_queued",
        repo_id=repo["id"],
        event_type=event_type,
        since_sha=since_sha[:8] if since_sha else None,
    )

    return {
        "received": True,
        "action":   "queued",
        "repo_id":  repo["id"],
        "event":    event_type,
    }

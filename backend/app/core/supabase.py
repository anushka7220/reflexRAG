# supabase.py
#
# WHY THIS FILE EXISTS:
# Creates and exposes Supabase client instances used across the entire app.
# Two clients exist for two different trust levels — see below.
#
# HOW TO USE:
#   from app.core.supabase import supabase_admin   # bypasses RLS — for system writes
#   from app.core.supabase import get_user_client  # respects RLS — for user-scoped reads

from supabase import create_client, Client
from functools import lru_cache
from app.core.config import settings


# ── Admin client (service_role key) ───────────────────────────────────────
#
# BYPASSES row-level security entirely.
# Use this ONLY for:
#   - Ingestion worker writing chunks, decision nodes, contributor data
#   - Webhook handlers updating repo status
#   - Background jobs that run as the system, not as a user
#
# NEVER use this in endpoints that return data to users —
# it would expose every user's data regardless of who's asking.

@lru_cache
def get_admin_client() -> Client:
    return create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SERVICE_ROLE_KEY,
    )

# Single instance imported by services that need system-level access
supabase_admin: Client = get_admin_client()


# ── User client factory (anon key + user JWT) ──────────────────────────────
#
# RESPECTS row-level security.
# Pass the user's JWT (extracted from the Authorization header) and Supabase
# will automatically enforce RLS — the client can only see rows where
# the policy allows that user's auth.uid().
#
# Use this in:
#   - Chat endpoints (user sees only their own sessions)
#   - Repo listing (user sees only their linked repos)
#   - Any endpoint that returns user-specific data
#
# WHY a factory function and not a singleton:
# Each user has a different JWT. We need a fresh client configured
# with that specific token per request. This is not cached.

def get_user_client(jwt: str) -> Client:
    """
    Returns a Supabase client scoped to the requesting user's JWT.
    RLS policies on the database will automatically restrict what this
    client can read and write.

    Args:
        jwt: The user's access token extracted from the Authorization header.
             Format: the raw token string, not "Bearer <token>".
    """
    client = create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_ANON_KEY,
    )
    # Inject the user's JWT so Supabase knows who is making the request.
    # This is what makes auth.uid() work inside RLS policies.
    client.auth.set_session(access_token=jwt, refresh_token="")
    return client


# ── Helper: execute a query and raise clearly on error ────────────────────
#
# Supabase-py returns a response object, not a direct result.
# Every query you run looks like:
#   response = supabase_admin.table("chunks").insert({...}).execute()
#
# If something goes wrong, the error is buried in response.
# This helper extracts the data or raises a clear Python exception.

def execute(response) -> list[dict]:
    """
    Unwraps a Supabase query response.
    Returns the data list on success, raises ValueError on failure.

    Usage:
        rows = execute(supabase_admin.table("repos").select("*").execute())
    """
    if hasattr(response, "error") and response.error:
        raise ValueError(f"Supabase query failed: {response.error.message}")
    return response.data

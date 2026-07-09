# dependencies.py
#
# WHY THIS FILE EXISTS:
# FastAPI dependency injection — reusable logic that runs before endpoint code.
# Instead of copy-pasting auth checks into every endpoint, we define them once
# here and declare them as dependencies where needed.
#
# HOW TO USE IN AN ENDPOINT:
#
#   from app.core.dependencies import get_current_user, require_pro
#   from app.models.user import UserProfile
#
#   @router.get("/repos")
#   async def list_repos(current_user: UserProfile = Depends(get_current_user)):
#       # current_user is already validated and fetched from DB
#       # if token was missing/invalid, FastAPI already returned 401
#       return current_user.repos
#
# FastAPI sees `Depends(get_current_user)`, runs that function first,
# and injects whatever it returns as `current_user`. Clean.

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.security import decode_access_token
from app.core.supabase import supabase_admin, execute
from app.models.user import UserProfile


# ── Token extractor ────────────────────────────────────────────────────────
#
# HTTPBearer reads the Authorization header and extracts the token.
# Format expected: "Authorization: Bearer <your_jwt>"
# If the header is missing or malformed, FastAPI returns 403 automatically.
#
# auto_error=True means FastAPI handles the missing header error for us.
# We don't need to check for it manually.

bearer_scheme = HTTPBearer(auto_error=True)


# ── Core dependency: get the current authenticated user ───────────────────
#
# This is the dependency every protected endpoint will use.
# It does three things in sequence:
#   1. Extracts JWT from Authorization header (via bearer_scheme)
#   2. Validates the JWT and extracts user_id
#   3. Fetches the full user profile from Supabase
#
# If any step fails, it raises HTTPException and the endpoint never runs.

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> UserProfile:
    """
    Validates the JWT and returns the authenticated user's profile.

    Raises:
        401 if token is invalid or expired.
        401 if user_id from token doesn't exist in our database.
    """
    # credentials.credentials is the raw token string (without "Bearer ")
    token = credentials.credentials

    # Validate the JWT and extract user_id
    user_id = decode_access_token(token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            # This header tells the client what auth scheme to use
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fetch user profile from database
    # We use admin client here because we're looking up by ID, not by RLS context
    response = supabase_admin.table("profiles").select("*").eq("id", user_id).execute()
    rows = execute(response)

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return UserProfile(**rows[0])


# ── Plan-gated dependency: free tier repo limit ────────────────────────────
#
# Use this on endpoints that create new repo ingestions.
# It checks whether the user has hit their free tier limit
# before the endpoint logic runs.

async def check_repo_limit(
    current_user: UserProfile = Depends(get_current_user),
) -> UserProfile:
    """
    Ensures the user hasn't exceeded their plan's repo limit.
    Pro users pass through unconditionally.
    Free users are blocked at FREE_TIER_REPOS_LIMIT.

    Raises:
        403 if free user has hit their repo limit.

    Returns:
        The same current_user — so endpoints get the user object too.

    Usage:
        @router.post("/repos")
        async def ingest_repo(current_user: UserProfile = Depends(check_repo_limit)):
            ...
    """
    from app.core.config import settings  # local import avoids circular import

    if current_user.plan == "pro":
        return current_user

    if current_user.repos_used >= settings.FREE_TIER_REPOS_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Free tier limit reached ({settings.FREE_TIER_REPOS_LIMIT} repos). "
                "Upgrade to pro for unlimited repos."
            ),
        )

    return current_user


# ── Plan-gated dependency: pro only ───────────────────────────────────────
#
# For features that are strictly pro-only (e.g. private repo ingestion).

async def require_pro(
    current_user: UserProfile = Depends(get_current_user),
) -> UserProfile:
    """
    Blocks free-tier users from accessing pro-only features.

    Raises:
        403 if user is on free plan.
    """
    if current_user.plan != "pro":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This feature requires a pro plan.",
        )
    return current_user


# ── Optional auth: endpoints accessible without login ─────────────────────
#
# Some endpoints work for both logged-in and anonymous users
# but behave differently. This dependency returns the user if
# authenticated, or None if not — without blocking the request.
#
# Example use case: a public repo preview page that shows less
# detail if you're not logged in.

async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(
        HTTPBearer(auto_error=False)  # auto_error=False means missing header returns None
    ),
) -> UserProfile | None:
    """
    Returns the current user if authenticated, None if not.
    Never raises 401 — lets the endpoint decide what to do with anonymous users.
    """
    if credentials is None:
        return None

    user_id = decode_access_token(credentials.credentials)
    if not user_id:
        return None

    response = supabase_admin.table("profiles").select("*").eq("id", user_id).execute()
    rows = execute(response)

    if not rows:
        return None

    return UserProfile(**rows[0])

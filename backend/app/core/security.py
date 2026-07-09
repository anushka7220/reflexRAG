# security.py
#
# WHY THIS FILE EXISTS:
# Handles two things:
#   1. GitHub OAuth flow — exchange GitHub code for user profile
#   2. JWT creation and validation — our own tokens we issue to the frontend
#
# FLOW:
#   User clicks "Login with GitHub"
#   → GitHub redirects to /auth/callback?code=xyz
#   → We exchange code for GitHub access token
#   → We use that token to fetch user's GitHub profile
#   → We create our own JWT with the user's id inside
#   → Frontend stores that JWT and sends it with every request
#   → We validate the JWT on every protected endpoint

import httpx
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from app.core.config import settings


# ── JWT config ─────────────────────────────────────────────────────────────
# ALGORITHM: HS256 means we sign the token with our SECRET_KEY.
# Anyone with the SECRET_KEY can verify the token is genuine.
# Never expose SECRET_KEY — that's why it lives in .env.
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days


# ── GitHub OAuth URLs ──────────────────────────────────────────────────────
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL  = "https://api.github.com/user"
GITHUB_EMAIL_URL = "https://api.github.com/user/emails"


# ── Step 1: Exchange GitHub code for GitHub access token ──────────────────
#
# When GitHub redirects back to /auth/callback, it includes a `code`
# query parameter. This code is short-lived (10 min) and single-use.
# We swap it for a GitHub access token that lets us call the GitHub API.

async def exchange_github_code(code: str) -> str:
    """
    Exchanges the OAuth code GitHub gave us for a GitHub access token.

    Args:
        code: The short-lived code from GitHub's redirect query param.

    Returns:
        GitHub access token string (used to call GitHub API as this user).

    Raises:
        ValueError if GitHub rejects the code.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GITHUB_TOKEN_URL,
            headers={"Accept": "application/json"},
            data={
                "client_id":     settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code":          code,
            },
        )
    data = response.json()

    # GitHub returns an error key instead of raising HTTP errors
    if "error" in data:
        raise ValueError(f"GitHub OAuth error: {data['error_description']}")

    return data["access_token"]


# ── Step 2: Fetch GitHub user profile ─────────────────────────────────────
#
# With the GitHub access token, we can call the GitHub API to get
# the user's profile — id, username, avatar, email.
# This is the only time we ever call GitHub for auth purposes.

async def fetch_github_user(github_token: str) -> dict:
    """
    Fetches the authenticated user's GitHub profile.

    Args:
        github_token: The GitHub access token from exchange_github_code().

    Returns:
        Dict with keys: id, login, avatar_url, email, name
    """
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
    }

    async with httpx.AsyncClient() as client:
        # Fetch main profile
        user_resp = await client.get(GITHUB_USER_URL, headers=headers)
        user_resp.raise_for_status()
        user = user_resp.json()

        # GitHub doesn't always return email in the main profile
        # if the user has set it to private. Fetch emails separately.
        if not user.get("email"):
            emails_resp = await client.get(GITHUB_EMAIL_URL, headers=headers)
            if emails_resp.status_code == 200:
                emails = emails_resp.json()
                # Pick the primary verified email
                primary = next(
                    (e["email"] for e in emails if e["primary"] and e["verified"]),
                    None,
                )
                user["email"] = primary

    return {
        "github_id":  str(user["id"]),
        "username":   user["login"],
        "avatar_url": user.get("avatar_url", ""),
        "email":      user.get("email", ""),
    }


# ── Step 3: Create our own JWT ─────────────────────────────────────────────
#
# We don't give the GitHub token to the frontend — we create our own JWT.
# WHY: Our JWT contains our user's UUID from Supabase, not GitHub's user ID.
# It also expires on our schedule, not GitHub's.
#
# A JWT has three parts: header.payload.signature
# The payload (claims) is visible to anyone — don't put secrets in it.
# The signature proves it wasn't tampered with — only we can create it.

def create_access_token(user_id: str) -> str:
    """
    Creates a signed JWT containing the user's Supabase UUID.

    Args:
        user_id: The UUID from our profiles table (not GitHub's user ID).

    Returns:
        Signed JWT string. Send this to the frontend.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    # Claims = the data inside the JWT payload
    # "sub" (subject) is the standard JWT claim for the user identifier
    # "exp" (expiry) is checked automatically by python-jose
    claims = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),  # issued at
    }

    return jwt.encode(claims, settings.SECRET_KEY, algorithm=ALGORITHM)


# ── Step 4: Validate JWT on every protected request ───────────────────────
#
# Every protected endpoint calls this to extract the user_id from the token.
# If the token is invalid, expired, or tampered with, this raises an error
# and the request is rejected before any business logic runs.

def decode_access_token(token: str) -> Optional[str]:
    """
    Validates a JWT and extracts the user_id (sub claim).

    Args:
        token: Raw JWT string from the Authorization header.
               Should be the token itself, not "Bearer <token>".

    Returns:
        user_id string if token is valid.
        None if token is invalid or expired.

    Usage in an endpoint:
        user_id = decode_access_token(token)
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
        return user_id
    except JWTError:
        # Covers: expired tokens, invalid signature, malformed token
        return None


# ── Webhook signature validation ───────────────────────────────────────────
#
# GitHub signs every webhook payload with GITHUB_WEBHOOK_SECRET using HMAC-SHA256.
# We must verify this signature before processing any webhook.
# Without this check, anyone could send fake webhook events to your endpoint.

import hmac
import hashlib

def verify_github_webhook(payload_bytes: bytes, signature_header: str) -> bool:
    """
    Verifies that a webhook payload was genuinely sent by GitHub.

    Args:
        payload_bytes:    Raw request body bytes.
        signature_header: The X-Hub-Signature-256 header value from GitHub.
                          Format: "sha256=<hex_digest>"

    Returns:
        True if signature is valid, False otherwise.

    Usage in webhook endpoint:
        body = await request.body()
        sig  = request.headers.get("X-Hub-Signature-256", "")
        if not verify_github_webhook(body, sig):
            raise HTTPException(status_code=403, detail="Invalid webhook signature")
    """
    if not signature_header.startswith("sha256="):
        return False

    expected_sig = signature_header[len("sha256="):]

    # Compute HMAC-SHA256 of the payload using our webhook secret
    mac = hmac.new(
        settings.GITHUB_WEBHOOK_SECRET.encode(),
        msg=payload_bytes,
        digestmod=hashlib.sha256,
    )
    actual_sig = mac.hexdigest()

    # compare_digest is timing-safe — prevents timing attacks
    # where an attacker measures response time to guess the secret
    return hmac.compare_digest(actual_sig, expected_sig)

#two things
#when user clicks "login with github", every request the frontend makes includes
#that JWT in the Authorization header so this file does both things- creating JWT
#and validating them as well

#oauth is two step handshake process- 1. temp code then 2. access token to fetch user data
#the access token never touches the url

#never give github token to the frontend, JWT contains database's UUID for user and this
#decouples auth from github

#JWT payload is not encrypted, just signed Anyone can decode a JWT and read {"sub": "uuid", "exp": 123...}.

import httpx
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from app.core.config import settings

# ALGORITHM: HS256 means we sign the token with our SECRET_KEY.
# Anyone with the SECRET_KEY can verify the token is genuine.
# Never expose SECRET_KEY — that's why it lives in .env.
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60*2487 # 7 DAYS

#github auth
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_EMAIL_URL = "https://api.github.com/user/emails"

#exchange github code for github access token
# When GitHub redirects back to /auth/callback, it includes a `code`
# query parameter. This code is short-lived (10 min) and single-use.
# We swap it for a GitHub access token that lets us call the GitHub API.
async def exchange_github_code(code: str) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GITHUB_TOKEN_URL,
            headers={"Accept": "application/json"},
            data={
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code": code,
            },
        )
    data =  response.json()
    #github returns an error key instead of raising http errors
    if "error" in data:
        raise ValueError(f"Github OAuth error: {data['error_description']}")
    
    return data["access_token"]

#fetch github user profile
async def fetch_github_user(github_token: str) -> dict:
    headers = {
        "Authentication": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
    }

    async with httpx.asyncClient() as client:
        #fetching main profile
        user_resp = await client.get(GITHUB_USER_URL, headers = headers)
        user_resp.raise_for_status()
        user = user_resp.json()

        #github doesn't always return email in the main profile
        #if the user has set it to private. Fetch emails separately
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

#clean our own JWT
#Our JWT contains our user's UUID from Supabase, not GitHub's user ID.
# A JWT has three parts: header.payload.signature
# The payload (claims) is visible to anyone — don't put secrets in it.
# The signature proves it wasn't tampered with — only we can create it.

def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    # "sub" (subject) is the standard JWT claim for the user identifier
    # "exp" (expiry) is checked automatically by python-jose
    claims = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),  # issued at
    }
 
    return jwt.encode(claims, settings.SECRET_KEY, algorithm=ALGORITHM)

#validate JWT on every protected request
 
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

#webhook signature validation
# GitHub signs every webhook payload with GITHUB_WEBHOOK_SECRET using HMAC-SHA256.
# We must verify this signature before processing any webhook.
# Without this check, anyone could send fake webhook events to your endpoint.
#hmac.compare_digest vs == — comparing strings with == short-circuits as soon as it finds a mismatch.
# An attacker can time thousands of requests and guess characters one by one. compare_digest always takes the same time regardless of where the mismatch is. This is called a timing-safe comparison 
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
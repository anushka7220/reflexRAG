# github_parser.py
#
# GitHub URL parsing utilities.
# Used by the orchestrator and ingestion routes to extract owner
# and repo name from a URL the user submits.

import re
from typing import Optional


def parse_github_url(url: str) -> Optional[tuple[str, str]]:
    """
    Parses a GitHub repo URL into (owner, repo_name).

    Accepts:
        https://github.com/owner/repo
        https://github.com/owner/repo/
        github.com/owner/repo

    Returns:
        (owner, repo_name) tuple, or None if the URL is invalid.
    """
    url = url.strip().rstrip("/")
    if not url.startswith("http"):
        url = "https://" + url

    pattern = r"https://github\.com/([\w\-\.]+)/([\w\-\.]+)"
    match = re.match(pattern, url)
    if not match:
        return None

    return match.group(1), match.group(2)

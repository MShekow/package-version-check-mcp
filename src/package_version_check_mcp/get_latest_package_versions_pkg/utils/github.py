"""GitHub utilities for fetching repository information."""

import os

import httpx

from ...utils.version_parser import Version, InvalidVersion


async def fetch_latest_github_tag(owner: str, repo: str, client: httpx.AsyncClient) -> tuple[str, str, str]:
    """Fetch the latest Git tag for a GitHub repository.

    Args:
        owner: The repository owner
        repo: The repository name
        client: httpx AsyncClient to use for requests

    Returns:
        A tuple of (tag_name, commit_sha, commit_date) e.g., ("v3.2.4", "abc123...", "2024-01-15T10:30:00Z")

    Raises:
        Exception: If tags cannot be fetched
    """
    # Use GitHub API to get tags
    url = f"https://api.github.com/repos/{owner}/{repo}/tags"

    response = await client.get(url)
    response.raise_for_status()
    tags = response.json()

    if not tags:
        raise ValueError(f"No tags found for {owner}/{repo}")

    # Default to the first tag if no stable version is found
    # This keeps specific behavior for repos that might only use prereleases or non-semver tags
    target_tag = tags[0]

    for tag in tags:
        try:
            version = Version(tag["name"])
            if not version.is_prerelease:
                target_tag = tag
                break
        except (InvalidVersion, ValueError):
            continue

    tag_name = target_tag["name"]
    commit_sha = target_tag["commit"]["sha"]

    # Fetch the commit details to get the date
    commit_url = f"https://api.github.com/repos/{owner}/{repo}/commits/{commit_sha}"
    commit_response = await client.get(commit_url)
    commit_response.raise_for_status()
    commit_data = commit_response.json()

    # Get the commit date (author date, not committer date)
    commit_date = commit_data["commit"]["author"]["date"]

    return tag_name, commit_sha, commit_date


def create_github_client(timeout: float = 30.0) -> httpx.AsyncClient:
    """Create an httpx AsyncClient configured for GitHub API requests.

    Args:
        timeout: Request timeout in seconds

    Returns:
        Configured httpx AsyncClient
    """
    headers = {"Accept": "application/vnd.github.v3+json"}
    github_pat = os.environ.get("GITHUB_PAT")
    if github_pat:
        headers["Authorization"] = f"token {github_pat}"

    return httpx.AsyncClient(timeout=timeout, headers=headers)

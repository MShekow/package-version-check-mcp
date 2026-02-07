from typing import Any, Optional

import httpx
import yaml

from .structs import GitHubActionResult, GitHubActionError
from ..get_latest_package_versions_pkg.utils.github import fetch_latest_github_tag, create_github_client


async def fetch_github_action_metadata(owner: str, repo: str, tag: str, client: httpx.AsyncClient) -> dict[str, Any]:
    """Fetch the action.yml metadata for a GitHub action.

    Args:
        owner: The repository owner
        repo: The repository name
        tag: The Git tag to fetch from
        client: httpx AsyncClient to use for requests

    Returns:
        Dict containing the parsed action.yml with inputs, outputs, and runs fields

    Raises:
        Exception: If action.yml cannot be fetched or parsed
    """
    # Try action.yml first, then action.yaml
    for filename in ["action.yml", "action.yaml"]:
        url = f"https://raw.githubusercontent.com/{owner}/{repo}/{tag}/{filename}"

        try:
            response = await client.get(url)
            response.raise_for_status()

            # Parse the YAML content
            action_data = yaml.safe_load(response.text)

            # Extract only the required fields
            metadata = {}
            if "inputs" in action_data:
                metadata["inputs"] = action_data["inputs"]
            if "outputs" in action_data:
                metadata["outputs"] = action_data["outputs"]
            if "runs" in action_data:
                metadata["runs"] = action_data["runs"]

            return metadata
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                continue  # Try the next filename
            raise

    raise ValueError(f"No action.yml or action.yaml found for {owner}/{repo}@{tag}")


async def fetch_github_action_readme(owner: str, repo: str, tag: str, client: httpx.AsyncClient) -> Optional[str]:
    """Fetch the README.md for a GitHub action.

    Args:
        owner: The repository owner
        repo: The repository name
        tag: The Git tag to fetch from
        client: httpx AsyncClient to use for requests

    Returns:
        The README content as a string, or None if not found

    Raises:
        Exception: If there's an error fetching the README (other than 404)
    """
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/{tag}/README.md"

    try:
        response = await client.get(url)
        response.raise_for_status()
        return response.text
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return None  # README not found, which is acceptable
        raise


async def fetch_github_action(action_name: str, include_readme: bool = False) -> GitHubActionResult | GitHubActionError:
    """Fetch information about a GitHub action.

    Args:
        action_name: The action name in format "owner/repo"
        include_readme: Whether to include the README content

    Returns:
        Either a GitHubActionResult on success or GitHubActionError on failure
    """
    try:
        # Parse the action name
        parts = action_name.split("/")
        if len(parts) != 2:
            raise ValueError(
                f"Invalid action name format: '{action_name}'. Expected 'owner/repo'"
            )

        owner, repo = parts

        async with create_github_client(timeout=30.0) as client:
            # Fetch the latest tag and its commit SHA (date is discarded for actions)
            latest_tag, commit_sha, _ = await fetch_latest_github_tag(owner, repo, client)

            # Fetch the action.yml metadata
            metadata = await fetch_github_action_metadata(owner, repo, latest_tag, client)

            # Optionally fetch the README
            readme = None
            if include_readme:
                readme = await fetch_github_action_readme(owner, repo, latest_tag, client)

            return GitHubActionResult(
                name=action_name,
                latest_version=latest_tag,
                digest=commit_sha,
                metadata=metadata,
                readme=readme,
            )

    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP error {e.response.status_code}: {e.response.reason_phrase}"
        if e.response.status_code == 404:
            error_msg = f"Action '{action_name}' not found on GitHub"
        return GitHubActionError(
            name=action_name,
            error=error_msg,
        )
    except Exception as e:
        return GitHubActionError(
            name=action_name,
            error=f"Failed to fetch GitHub action: {str(e)}",
        )

from typing import Any, Optional

from pydantic import BaseModel


class GitHubActionResult(BaseModel):
    """Successful GitHub action lookup result."""

    name: str
    latest_version: str
    digest: str  # Commit SHA that the tag points to
    metadata: dict[str, Any]  # action.yml fields: inputs, outputs, runs
    readme: Optional[str] = None


class GitHubActionError(BaseModel):
    """Error during GitHub action lookup."""

    name: str
    error: str


class GetGitHubActionVersionsResponse(BaseModel):
    """Response from get_github_action_versions_and_args tool."""

    result: list[GitHubActionResult]
    lookup_errors: list[GitHubActionError]

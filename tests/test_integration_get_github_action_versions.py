"""Tests for GitHub Actions version lookup."""

import pytest
from fastmcp import Client

from package_version_check_mcp.main import (
    mcp,
)
from package_version_check_mcp.get_github_actions_pkg.structs import GetGitHubActionVersionsResponse


@pytest.fixture
async def mcp_client():
    """Create a FastMCP client for testing."""
    async with Client(mcp) as client:
        yield client


@pytest.mark.parametrize("include_readme", [False, True])
async def test_get_github_action_versions_readme(mcp_client: Client, include_readme: bool):
    """Test fetching GitHub action versions with and without README."""
    result = await mcp_client.call_tool(
        name="get_github_action_versions_and_args",
        arguments={
            "action_names": ["actions/checkout"],
            "include_readme": include_readme,
        },
    )

    assert result.structured_content is not None
    response = GetGitHubActionVersionsResponse.model_validate(result.structured_content)
    assert len(response.result) == 1
    assert len(response.lookup_errors) == 0

    action_data = response.result[0]
    assert action_data.name == "actions/checkout"
    assert action_data.latest_version.startswith("v")  # Should be like "v4.2.1"
    assert action_data.digest is not None
    assert len(action_data.digest) == 40  # SHA-1 hash is 40 hex characters
    assert "inputs" in action_data.metadata
    assert "runs" in action_data.metadata

    if include_readme:
        assert action_data.readme is not None
        assert len(action_data.readme) > 0
        assert "checkout" in action_data.readme.lower()
    else:
        assert action_data.readme is None


@pytest.mark.parametrize("action_names", [
    ["actions/checkout"],
    ["actions/checkout", "actions/setup-python"],
    ["actions/checkout", "actions/setup-python", "actions/setup-node"],
])
async def test_get_github_action_versions_multiple(mcp_client: Client, action_names: list[str]):
    """Test fetching multiple GitHub actions."""
    result = await mcp_client.call_tool(
        name="get_github_action_versions_and_args",
        arguments={
            "action_names": action_names,
            "include_readme": False,
        },
    )

    assert result.structured_content is not None
    response = GetGitHubActionVersionsResponse.model_validate(result.structured_content)
    assert len(response.result) == len(action_names)
    assert len(response.lookup_errors) == 0

    names = {action.name for action in response.result}
    assert names == set(action_names)

    for action_data in response.result:
        assert action_data.latest_version.startswith("v")
        assert action_data.digest is not None
        assert len(action_data.digest) == 40  # SHA-1 hash is 40 hex characters
        assert "runs" in action_data.metadata


@pytest.mark.parametrize("action_name,error_substring", [
    ("nonexistent-owner/nonexistent-repo-xyz123", "not found"),
    ("invalid-format", "invalid"),
])
async def test_get_github_action_versions_errors(mcp_client: Client, action_name: str, error_substring: str):
    """Test handling of various error cases."""
    result = await mcp_client.call_tool(
        name="get_github_action_versions_and_args",
        arguments={
            "action_names": [action_name],
            "include_readme": False,
        },
    )

    assert result.structured_content is not None
    response = GetGitHubActionVersionsResponse.model_validate(result.structured_content)
    assert len(response.result) == 0
    assert len(response.lookup_errors) == 1

    error = response.lookup_errors[0]
    assert error.name == action_name
    assert error_substring in error.error.lower()


async def test_get_github_action_versions_mixed(mcp_client: Client):
    """Test fetching with both successful and failed lookups."""
    result = await mcp_client.call_tool(
        name="get_github_action_versions_and_args",
        arguments={
            "action_names": ["actions/checkout", "nonexistent/action"],
            "include_readme": False,
        },
    )

    assert result.structured_content is not None
    response = GetGitHubActionVersionsResponse.model_validate(result.structured_content)
    assert len(response.result) == 1
    assert len(response.lookup_errors) == 1

    assert response.result[0].name == "actions/checkout"
    assert response.lookup_errors[0].name == "nonexistent/action"

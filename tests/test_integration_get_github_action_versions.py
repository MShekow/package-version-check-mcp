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


async def test_get_github_action_versions_basic(mcp_client: Client):
    """Test fetching GitHub action versions without README."""
    result = await mcp_client.call_tool(
        name="get_github_action_versions_and_args",
        arguments={
            "action_names": ["actions/checkout"],
            "include_readme": False,
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
    assert action_data.readme is None


async def test_get_github_action_versions_with_readme(mcp_client: Client):
    """Test fetching GitHub action versions with README."""
    result = await mcp_client.call_tool(
        name="get_github_action_versions_and_args",
        arguments={
            "action_names": ["actions/checkout"],
            "include_readme": True,
        },
    )

    assert result.structured_content is not None
    response = GetGitHubActionVersionsResponse.model_validate(result.structured_content)
    assert len(response.result) == 1
    action_data = response.result[0]
    assert action_data.readme is not None
    assert len(action_data.readme) > 0
    assert "checkout" in action_data.readme.lower()


async def test_get_github_action_versions_multiple(mcp_client: Client):
    """Test fetching multiple GitHub actions."""
    result = await mcp_client.call_tool(
        name="get_github_action_versions_and_args",
        arguments={
            "action_names": ["actions/checkout", "actions/setup-python"],
            "include_readme": False,
        },
    )

    assert result.structured_content is not None
    response = GetGitHubActionVersionsResponse.model_validate(result.structured_content)
    assert len(response.result) == 2
    assert len(response.lookup_errors) == 0

    names = {action.name for action in response.result}
    assert names == {"actions/checkout", "actions/setup-python"}

    for action_data in response.result:
        assert action_data.latest_version.startswith("v")
        assert action_data.digest is not None
        assert len(action_data.digest) == 40  # SHA-1 hash is 40 hex characters
        assert "runs" in action_data.metadata


async def test_get_github_action_versions_not_found(mcp_client: Client):
    """Test handling of non-existent GitHub action."""
    result = await mcp_client.call_tool(
        name="get_github_action_versions_and_args",
        arguments={
            "action_names": ["nonexistent-owner/nonexistent-repo-xyz123"],
            "include_readme": False,
        },
    )

    assert result.structured_content is not None
    response = GetGitHubActionVersionsResponse.model_validate(result.structured_content)
    assert len(response.result) == 0
    assert len(response.lookup_errors) == 1

    error = response.lookup_errors[0]
    assert error.name == "nonexistent-owner/nonexistent-repo-xyz123"
    assert "not found" in error.error.lower()


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


async def test_get_github_action_versions_invalid_format(mcp_client: Client):
    """Test handling of invalid action name format."""
    result = await mcp_client.call_tool(
        name="get_github_action_versions_and_args",
        arguments={
            "action_names": ["invalid-format"],
            "include_readme": False,
        },
    )

    assert result.structured_content is not None
    response = GetGitHubActionVersionsResponse.model_validate(result.structured_content)
    assert len(response.result) == 0
    assert len(response.lookup_errors) == 1

    error = response.lookup_errors[0]
    assert error.name == "invalid-format"
    assert "invalid" in error.error.lower()

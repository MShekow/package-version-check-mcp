"""Tests for GitHub Actions version lookup."""

import pytest
from fastmcp import Client

from package_version_check_mcp.main import (
    mcp,
)
from package_version_check_mcp.get_github_actions_pkg.structs import GetGitHubActionVersionsResponse
from package_version_check_mcp.utils.version_parser import Version


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
    assert len(response.result) == 1, \
        f"Expected 1 result, got {len(response.result)}: {response.result}. " \
        f"Errors: {response.lookup_errors}"
    assert len(response.lookup_errors) == 0, \
        f"Expected 0 errors, got {len(response.lookup_errors)}: {response.lookup_errors}"

    action_data = response.result[0]
    assert action_data.name == "actions/checkout"
    assert action_data.latest_version.startswith("v"), f"Version should start with 'v': {action_data.latest_version}"
    assert action_data.digest is not None
    assert len(action_data.digest) == 40, f"Digest should be 40 chars (SHA-1): {action_data.digest}"
    assert "inputs" in action_data.metadata, f"Metadata keys: {action_data.metadata.keys()}"
    assert "runs" in action_data.metadata, f"Metadata keys: {action_data.metadata.keys()}"

    if include_readme:
        assert action_data.readme is not None
        assert len(action_data.readme) > 0
        assert "checkout" in action_data.readme.lower(), \
            f"'checkout' not in readme: {action_data.readme[:100]}..."
    else:
        assert action_data.readme is None


@pytest.mark.parametrize("action_names,minimum_expected_versions", [
    (["actions/checkout"], ["v6.0.2"]),
    (["anothrNick/github-tag-action"], ["1.75.0"]),
    (["actions/checkout", "actions/setup-python"], ["v6.0.2", "v6.2.0"]),
    (["actions/checkout", "actions/setup-python", "actions/setup-node"], ["v6.0.2", "v6.2.0", "v6.2.0"]),
])
async def test_get_github_action_versions_multiple(mcp_client: Client, action_names: list[str], minimum_expected_versions: list[str]):
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
    assert len(response.result) == len(action_names), \
        f"Expected {len(action_names)} results, got {len(response.result)}: {response.result}. " \
        f"Errors: {response.lookup_errors}"
    assert len(response.lookup_errors) == 0, \
        f"Expected 0 errors, got {len(response.lookup_errors)}: {response.lookup_errors}"

    names = {action.name for action in response.result}
    assert names == set(action_names), f"Got action names: {names}"

    # Create a mapping of action names to minimum expected versions
    name_to_min_version = {name: min_ver for name, min_ver in zip(action_names, minimum_expected_versions)}

    for action_data in response.result:
        assert action_data.latest_version[0].isdigit() or action_data.latest_version.startswith("v"), \
            f"Version should start with 'v' or a digit ({action_data.name}): {action_data.latest_version}"
        assert action_data.digest is not None
        assert len(action_data.digest) == 40, f"Digest should be 40 chars ({action_data.name}): {action_data.digest}"
        assert "runs" in action_data.metadata, f"Metadata keys ({action_data.name}): {action_data.metadata.keys()}"

        # Compare version against minimum expected version
        minimum_expected_version_obj = Version(name_to_min_version[action_data.name])
        latest_version = Version(action_data.latest_version)
        assert latest_version >= minimum_expected_version_obj, \
            f"Expected version >= {name_to_min_version[action_data.name]}, got {action_data.latest_version} for {action_data.name}"


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
    assert len(response.result) == 0, \
        f"Expected 0 results, got {len(response.result)}: {response.result}. " \
        f"Errors: {response.lookup_errors}"
    assert len(response.lookup_errors) == 1, \
        f"Expected 1 error, got {len(response.lookup_errors)}: {response.lookup_errors}. " \
        f"Results: {response.result}"

    error = response.lookup_errors[0]
    assert error.name == action_name
    assert error_substring in error.error.lower(), f"Expected '{error_substring}' in error: {error.error}"


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
    assert len(response.result) == 1, \
        f"Expected 1 result, got {len(response.result)}: {response.result}. " \
        f"Errors: {response.lookup_errors}"
    assert len(response.lookup_errors) == 1, \
        f"Expected 1 error, got {len(response.lookup_errors)}: {response.lookup_errors}"

    assert response.result[0].name == "actions/checkout"
    assert response.lookup_errors[0].name == "nonexistent/action"

"""Tests for the package version check MCP server."""

import pytest
from fastmcp import Client

from package_version_check_mcp.main import (
    mcp,
)
from package_version_check_mcp.get_latest_versions_pkg.structs import Ecosystem, PackageVersionRequest, \
    GetLatestVersionsResponse


@pytest.fixture
async def mcp_client():
    """Create a FastMCP client for testing."""
    async with Client(mcp) as client:
        yield client


@pytest.mark.parametrize("ecosystem,package_name", [
    (Ecosystem.NPM, "express"),
    (Ecosystem.PYPI, "requests"),
])
async def test_get_latest_versions_success(mcp_client: Client, ecosystem, package_name):
    """Test fetching valid package versions from different ecosystems."""
    result = await mcp_client.call_tool(
        name="get_latest_versions",
        arguments={
            "packages": [
                PackageVersionRequest(ecosystem=ecosystem, package_name=package_name)
            ]
        }
    )

    assert result.structured_content is not None
    response = GetLatestVersionsResponse.model_validate(result.structured_content)
    assert len(response.result) == 1
    assert response.result[0].ecosystem == ecosystem.value
    assert response.result[0].package_name == package_name
    assert response.result[0].latest_version != ""
    assert "." in response.result[0].latest_version
    assert response.result[0].published_on is not None
    assert len(response.lookup_errors) == 0


@pytest.mark.parametrize("ecosystem", [Ecosystem.NPM, Ecosystem.PYPI])
async def test_get_latest_versions_not_found(mcp_client: Client, ecosystem):
    """Test fetching non-existent packages from different ecosystems."""
    package_name = "this-package-definitely-does-not-exist-12345678"
    result = await mcp_client.call_tool(
        name="get_latest_versions",
        arguments={
            "packages": [
                PackageVersionRequest(ecosystem=ecosystem, package_name=package_name)
            ]
        }
    )

    assert result.structured_content is not None
    response = GetLatestVersionsResponse.model_validate(result.structured_content)
    assert len(response.result) == 0
    assert len(response.lookup_errors) == 1
    assert response.lookup_errors[0].ecosystem == ecosystem.value
    assert response.lookup_errors[0].package_name == package_name
    assert "not found" in response.lookup_errors[0].error.lower()


async def test_get_latest_versions_mixed_success_and_failure(mcp_client: Client):
    """Test get_latest_versions with both valid and invalid packages."""
    result = await mcp_client.call_tool(
        name="get_latest_versions",
        arguments={
            "packages": [
                PackageVersionRequest(ecosystem=Ecosystem.NPM, package_name="express"),
                PackageVersionRequest(ecosystem=Ecosystem.PYPI, package_name="requests"),
                PackageVersionRequest(ecosystem=Ecosystem.NPM, package_name="this-does-not-exist-99999"),
                PackageVersionRequest(ecosystem=Ecosystem.PYPI, package_name="this-also-does-not-exist-99999"),
            ]
        }
    )

    assert result.structured_content is not None
    response = GetLatestVersionsResponse.model_validate(result.structured_content)
    # Should have 2 successful results
    assert len(response.result) == 2
    assert response.result[0].package_name == "express"
    assert response.result[0].ecosystem == "npm"
    assert response.result[1].package_name == "requests"
    assert response.result[1].ecosystem == "pypi"

    # Should have 2 errors
    assert len(response.lookup_errors) == 2
    assert all("not found" in err.error.lower() for err in response.lookup_errors)


async def test_get_latest_versions_empty_input(mcp_client: Client):
    """Test get_latest_versions with empty input."""
    result = await mcp_client.call_tool(
        name="get_latest_versions",
        arguments={"packages": []}
    )

    assert result.structured_content is not None
    response = GetLatestVersionsResponse.model_validate(result.structured_content)
    assert len(response.result) == 0
    assert len(response.lookup_errors) == 0


async def test_get_latest_versions_multiple_packages(mcp_client: Client):
    """Test get_latest_versions with multiple valid packages."""
    result = await mcp_client.call_tool(
        name="get_latest_versions",
        arguments={
            "packages": [
                PackageVersionRequest(ecosystem=Ecosystem.NPM, package_name="express"),
                PackageVersionRequest(ecosystem=Ecosystem.NPM, package_name="react"),
                PackageVersionRequest(ecosystem=Ecosystem.PYPI, package_name="requests"),
                PackageVersionRequest(ecosystem=Ecosystem.PYPI, package_name="flask"),
            ]
        }
    )

    assert result.structured_content is not None
    response = GetLatestVersionsResponse.model_validate(result.structured_content)
    assert len(response.result) == 4
    assert len(response.lookup_errors) == 0

    # Verify all packages are present
    package_names = {pkg.package_name for pkg in response.result}
    assert package_names == {"express", "react", "requests", "flask"}

    # Verify all have valid versions
    for pkg in response.result:
        assert pkg.latest_version != ""
        assert "." in pkg.latest_version

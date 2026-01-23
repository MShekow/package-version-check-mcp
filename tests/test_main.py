"""Tests for the package version check MCP server."""

import pytest
from fastmcp import Client

from package_version_check_mcp.main import mcp


@pytest.fixture
async def mcp_client():
    """Create a FastMCP client for testing."""
    async with Client(mcp) as client:
        yield client


@pytest.mark.asyncio
async def test_get_latest_versions_npm_success(mcp_client: Client):
    """Test fetching a valid NPM package version."""
    result = await mcp_client.call_tool(
        name="get_latest_versions",
        arguments={
            "packages": [
                {"ecosystem": "npm", "package_name": "express"}
            ]
        }
    )

    assert result.data is not None
    assert len(result.data.result) == 1
    assert result.data.result[0].ecosystem == "npm"
    assert result.data.result[0].package_name == "express"
    assert result.data.result[0].latest_version != ""
    # Express should have a version like "4.x.x" or "5.x.x"
    assert "." in result.data.result[0].latest_version
    # Should have a publication date
    assert result.data.result[0].published_on is not None
    assert len(result.data.lookup_errors) == 0


@pytest.mark.asyncio
async def test_get_latest_versions_pypi_success(mcp_client: Client):
    """Test fetching a valid PyPI package version."""
    result = await mcp_client.call_tool(
        name="get_latest_versions",
        arguments={
            "packages": [
                {"ecosystem": "pypi", "package_name": "requests"}
            ]
        }
    )

    assert result.data is not None
    assert len(result.data.result) == 1
    assert result.data.result[0].ecosystem == "pypi"
    assert result.data.result[0].package_name == "requests"
    assert result.data.result[0].latest_version != ""
    # Requests should have a version with dots
    assert "." in result.data.result[0].latest_version
    # Should have a publication date
    assert result.data.result[0].published_on is not None
    assert len(result.data.lookup_errors) == 0


async def test_get_latest_versions_npm_not_found(mcp_client: Client):
    """Test fetching a non-existent NPM package."""
    result = await mcp_client.call_tool(
        name="get_latest_versions",
        arguments={
            "packages": [
                {"ecosystem": "npm", "package_name": "this-package-definitely-does-not-exist-12345678"}
            ]
        }
    )

    assert result.data is not None
    assert len(result.data.result) == 0
    assert len(result.data.lookup_errors) == 1
    assert result.data.lookup_errors[0].ecosystem == "npm"
    assert result.data.lookup_errors[0].package_name == "this-package-definitely-does-not-exist-12345678"
    assert "not found" in result.data.lookup_errors[0].error.lower()


async def test_get_latest_versions_pypi_not_found(mcp_client: Client):
    """Test fetching a non-existent PyPI package."""
    result = await mcp_client.call_tool(
        name="get_latest_versions",
        arguments={
            "packages": [
                {"ecosystem": "pypi", "package_name": "this-package-definitely-does-not-exist-12345678"}
            ]
        }
    )

    assert result.data is not None
    assert len(result.data.result) == 0
    assert len(result.data.lookup_errors) == 1
    assert result.data.lookup_errors[0].ecosystem == "pypi"
    assert result.data.lookup_errors[0].package_name == "this-package-definitely-does-not-exist-12345678"
    assert "not found" in result.data.lookup_errors[0].error.lower()


async def test_get_latest_versions_mixed_success_and_failure(mcp_client: Client):
    """Test get_latest_versions with both valid and invalid packages."""
    result = await mcp_client.call_tool(
        name="get_latest_versions",
        arguments={
            "packages": [
                {"ecosystem": "npm", "package_name": "express"},
                {"ecosystem": "pypi", "package_name": "requests"},
                {"ecosystem": "npm", "package_name": "this-does-not-exist-99999"},
                {"ecosystem": "pypi", "package_name": "this-also-does-not-exist-99999"},
            ]
        }
    )

    assert result.data is not None
    # Should have 2 successful results
    assert len(result.data.result) == 2
    assert result.data.result[0].package_name == "express"
    assert result.data.result[0].ecosystem == "npm"
    assert result.data.result[1].package_name == "requests"
    assert result.data.result[1].ecosystem == "pypi"

    # Should have 2 errors
    assert len(result.data.lookup_errors) == 2
    assert all("not found" in err.error.lower() for err in result.data.lookup_errors)


@pytest.mark.asyncio
async def test_get_latest_versions_empty_input(mcp_client: Client):
    """Test get_latest_versions with empty input."""
    result = await mcp_client.call_tool(
        name="get_latest_versions",
        arguments={"packages": []}
    )

    assert result.data is not None
    assert len(result.data.result) == 0
    assert len(result.data.lookup_errors) == 0


@pytest.mark.asyncio
async def test_get_latest_versions_multiple_packages(mcp_client: Client):
    """Test get_latest_versions with multiple valid packages."""
    result = await mcp_client.call_tool(
        name="get_latest_versions",
        arguments={
            "packages": [
                {"ecosystem": "npm", "package_name": "express"},
                {"ecosystem": "npm", "package_name": "react"},
                {"ecosystem": "pypi", "package_name": "requests"},
                {"ecosystem": "pypi", "package_name": "flask"},
            ]
        }
    )

    assert result.data is not None
    assert len(result.data.result) == 4
    assert len(result.data.lookup_errors) == 0

    # Verify all packages are present
    package_names = {pkg.package_name for pkg in result.data.result}
    assert package_names == {"express", "react", "requests", "flask"}

    # Verify all have valid versions
    for pkg in result.data.result:
        assert pkg.latest_version != ""
        assert "." in pkg.latest_version

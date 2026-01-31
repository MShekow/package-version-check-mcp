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
    (Ecosystem.PyPI, "requests"),
    (Ecosystem.Docker, "index.docker.io/library/busybox"),
    (Ecosystem.NuGet, "Newtonsoft.Json"),
    (Ecosystem.MavenGradle, "org.springframework:spring-core"),
    (Ecosystem.MavenGradle, "com.google.guava:guava"),
    (Ecosystem.MavenGradle, "org.apache.commons:commons-lang3"),
    (Ecosystem.Helm, "https://charts.bitnami.com/bitnami/nginx"),
    (Ecosystem.Helm, "https://charts.bitnami.com/bitnami/redis"),
    (Ecosystem.Helm, "https://prometheus-community.github.io/helm-charts/prometheus"),
    (Ecosystem.Helm, "oci://ghcr.io/argoproj/argo-helm/argo-cd"),
    (Ecosystem.Helm, "oci://registry-1.docker.io/bitnamicharts/nginx"),
    (Ecosystem.TerraformProvider, "hashicorp/aws"),
    (Ecosystem.TerraformProvider, "hashicorp/google"),
    (Ecosystem.TerraformProvider, "registry.terraform.io/hashicorp/azurerm"),
    (Ecosystem.TerraformProvider, "registry.opentofu.org/hashicorp/random"),
    (Ecosystem.TerraformModule, "terraform-aws-modules/vpc/aws"),
    (Ecosystem.TerraformModule, "terraform-aws-modules/eks/aws"),
    (Ecosystem.TerraformModule, "registry.terraform.io/Azure/network/azurerm"),
    (Ecosystem.Go, "github.com/gin-gonic/gin"),
    (Ecosystem.Go, "github.com/google/uuid"),
    (Ecosystem.PHP, "monolog/monolog"),
    (Ecosystem.PHP, "laravel/framework"),
    (Ecosystem.PHP, "symfony/console"),
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
    assert response.result[0].ecosystem is ecosystem
    assert response.result[0].package_name == package_name
    assert "." in response.result[0].latest_version

    if ecosystem is Ecosystem.Docker:
        assert response.result[0].digest is not None
        assert response.result[0].digest.startswith("sha256:")

    if ecosystem is Ecosystem.MavenGradle:
        # Maven/Gradle doesn't provide digest or published_on
        assert response.result[0].digest is None
        assert response.result[0].published_on is None

    if ecosystem is Ecosystem.Go:
        assert response.result[0].published_on is not None
        assert response.result[0].digest is not None

    if ecosystem is Ecosystem.PHP:
        # PHP packages should have published_on but no digest
        assert response.result[0].published_on is not None
        assert response.result[0].digest is None

    assert len(response.lookup_errors) == 0


@pytest.mark.parametrize("ecosystem,package_name", [
    (Ecosystem.NPM, "this-package-definitely-does-not-exist-12345678"),
    (Ecosystem.PyPI, "this-package-definitely-does-not-exist-12345678"),
    (Ecosystem.NuGet, "this-package-definitely-does-not-exist-12345678"),
    (Ecosystem.MavenGradle, "org.nonexistent:this-package-definitely-does-not-exist-12345678"),
    (Ecosystem.Helm, "https://charts.bitnami.com/bitnami/nonexistent-chart-12345"),
    (Ecosystem.Helm, "oci://ghcr.io/nonexistent-org-12345/nonexistent-chart-12345"),
    (Ecosystem.TerraformProvider, "nonexistent-namespace-12345/nonexistent-provider-12345"),
    (Ecosystem.TerraformModule, "nonexistent-namespace-12345/nonexistent-module-12345/aws"),
    (Ecosystem.Go, "github.com/nonexistent-user-12345/nonexistent-repo-12345"),
    (Ecosystem.PHP, "nonexistent-vendor-12345/nonexistent-package-12345"),
])
async def test_get_latest_versions_not_found(mcp_client: Client, ecosystem, package_name):
    """Test fetching non-existent packages from different ecosystems."""
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
    assert response.lookup_errors[0].ecosystem is ecosystem
    assert response.lookup_errors[0].package_name == package_name
    # Different registries return different errors (404 Not Found, 403 Forbidden, etc.)
    error_lower = response.lookup_errors[0].error.lower()
    assert "not found" in error_lower or "403" in error_lower or "forbidden" in error_lower


async def test_get_latest_versions_mixed_success_and_failure(mcp_client: Client):
    """Test get_latest_versions with both valid and invalid packages."""
    result = await mcp_client.call_tool(
        name="get_latest_versions",
        arguments={
            "packages": [
                PackageVersionRequest(ecosystem=Ecosystem.NPM, package_name="express"),
                PackageVersionRequest(ecosystem=Ecosystem.PyPI, package_name="requests"),
                PackageVersionRequest(ecosystem=Ecosystem.NPM, package_name="this-does-not-exist-99999"),
                PackageVersionRequest(ecosystem=Ecosystem.PyPI, package_name="this-also-does-not-exist-99999"),
            ]
        }
    )

    assert result.structured_content is not None
    response = GetLatestVersionsResponse.model_validate(result.structured_content)
    # Should have 2 successful results
    assert len(response.result) == 2
    assert response.result[0].package_name == "express"
    assert response.result[0].ecosystem is Ecosystem.NPM
    assert response.result[1].package_name == "requests"
    assert response.result[1].ecosystem is Ecosystem.PyPI

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
                PackageVersionRequest(ecosystem=Ecosystem.PyPI, package_name="requests"),
                PackageVersionRequest(ecosystem=Ecosystem.PyPI, package_name="flask"),
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


@pytest.mark.parametrize("package_name,version_hint,expected_suffix", [
    ("index.docker.io/library/busybox", "1.36-musl", "musl"),
    ("index.docker.io/library/busybox", "1.36-glibc", "glibc"),
    ("index.docker.io/library/memcached", "1-bookworm", "bookworm"),
])
async def test_get_latest_versions_docker_with_tag_hint(mcp_client: Client, package_name, version_hint, expected_suffix):
    """Test fetching Docker image versions with tag compatibility hint."""
    result = await mcp_client.call_tool(
        name="get_latest_versions",
        arguments={
            "packages": [
                PackageVersionRequest(
                    ecosystem=Ecosystem.Docker,
                    package_name=package_name,
                    version_hint=version_hint
                )
            ]
        }
    )

    assert result.structured_content is not None
    response = GetLatestVersionsResponse.model_validate(result.structured_content)
    assert len(response.result) == 1
    assert response.result[0].ecosystem is Ecosystem.Docker
    assert response.result[0].package_name == package_name
    assert "." in response.result[0].latest_version
    # The returned tag should have the same suffix
    assert expected_suffix in response.result[0].latest_version.lower()
    # Should have a digest
    assert response.result[0].digest is not None
    assert response.result[0].digest.startswith("sha256:")
    assert len(response.lookup_errors) == 0


@pytest.mark.parametrize("package_name,version_hint", [
    ("monolog/monolog", "php:8.1"),
    ("monolog/monolog", "8.2"),
    ("symfony/console", "php:8.1"),
])
async def test_get_latest_versions_php_with_version_hint(mcp_client: Client, package_name, version_hint):
    """Test fetching PHP package versions with PHP version compatibility hint."""
    result = await mcp_client.call_tool(
        name="get_latest_versions",
        arguments={
            "packages": [
                PackageVersionRequest(
                    ecosystem=Ecosystem.PHP,
                    package_name=package_name,
                    version_hint=version_hint
                )
            ]
        }
    )

    assert result.structured_content is not None
    response = GetLatestVersionsResponse.model_validate(result.structured_content)
    assert len(response.result) == 1
    assert response.result[0].ecosystem is Ecosystem.PHP
    assert response.result[0].package_name == package_name
    assert "." in response.result[0].latest_version
    # PHP packages should have published_on but no digest
    assert response.result[0].published_on is not None
    assert response.result[0].digest is None
    assert len(response.lookup_errors) == 0

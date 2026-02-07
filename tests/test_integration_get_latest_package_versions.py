"""Tests for the package version check MCP server."""

import pytest
from pytest_mock import MockerFixture
from fastmcp import Client

from package_version_check_mcp.main import (
    mcp,
)
from package_version_check_mcp.get_latest_package_versions_pkg.structs import Ecosystem, PackageVersionRequest, \
    GetLatestVersionsResponse, PackageVersionResult
from package_version_check_mcp.utils.version_parser import Version
from package_version_check_mcp.get_latest_package_versions_pkg.dispatcher import fetch_package_version, _version_cache


@pytest.fixture
async def mcp_client():
    """Create a FastMCP client for testing."""
    async with Client(mcp) as client:
        yield client


@pytest.mark.parametrize("ecosystem,package_name,minimum_expected_version", [
    (Ecosystem.NPM, "express", "5.2.1"),
    (Ecosystem.PyPI, "requests", "2.32.5"),
    (Ecosystem.Docker, "index.docker.io/library/busybox", "1.37.0"),
    (Ecosystem.NuGet, "Newtonsoft.Json", "13.0.4"),
    (Ecosystem.MavenGradle, "org.springframework:spring-core", "7.0.3"),
    (Ecosystem.MavenGradle, "com.google.guava:guava", "33.5.0-jre"),
    (Ecosystem.MavenGradle, "org.apache.commons:commons-lang3", "3.20.0"),
    (Ecosystem.MavenGradle, "org.springframework.boot:spring-boot-starter-parent", "4.0.2"),
    (Ecosystem.Helm, "https://charts.bitnami.com/bitnami/nginx", "22.4.3"),
    (Ecosystem.Helm, "https://charts.bitnami.com/bitnami/redis", "24.1.2"),
    (Ecosystem.Helm, "https://prometheus-community.github.io/helm-charts/prometheus", "28.7.0"),
    (Ecosystem.Helm, "oci://ghcr.io/argoproj/argo-helm/argo-cd", "9.3.7"),
    (Ecosystem.Helm, "oci://registry-1.docker.io/bitnamicharts/nginx", "22.4.3"),
    (Ecosystem.TerraformProvider, "hashicorp/aws", "6.30.0"),
    (Ecosystem.TerraformProvider, "hashicorp/google", "7.17.0"),
    (Ecosystem.TerraformProvider, "registry.terraform.io/hashicorp/azurerm", "4.58.0"),
    (Ecosystem.TerraformProvider, "registry.opentofu.org/hashicorp/random", "3.8.1"),
    (Ecosystem.TerraformModule, "terraform-aws-modules/vpc/aws", "6.6.0"),
    (Ecosystem.TerraformModule, "terraform-aws-modules/eks/aws", "21.15.1"),
    (Ecosystem.TerraformModule, "registry.terraform.io/Azure/network/azurerm", "5.3.0"),
    (Ecosystem.Go, "github.com/gin-gonic/gin", "v1.11.0"),
    (Ecosystem.Go, "github.com/google/uuid", "v1.6.0"),
    (Ecosystem.PHP, "monolog/monolog", "3.10.0"),
    (Ecosystem.PHP, "laravel/framework", "v12.49.0"),
    (Ecosystem.PHP, "symfony/console", "v8.0.4"),
    (Ecosystem.RubyGems, "rails", "8.1.2"),
    (Ecosystem.RubyGems, "devise", "5.0.0"),
    (Ecosystem.RubyGems, "rspec", "3.13.2"),
    (Ecosystem.Rust, "serde", "1.0.228"),
    (Ecosystem.Rust, "tokio", "1.49.0"),
    (Ecosystem.Rust, "clap", "4.5.56"),
    (Ecosystem.Swift, "https://github.com/Alamofire/Alamofire.git", "5.11.1"),
    (Ecosystem.Swift, "https://github.com/Moya/Moya.git", "15.0.3"),
    (Ecosystem.Dart, "http", "1.6.0"),
    (Ecosystem.Dart, "path", "1.9.1"),
])
async def test_get_latest_package_versions_success(mcp_client: Client, ecosystem: Ecosystem, package_name: str,
                                                   minimum_expected_version: str):
    """Test fetching valid package versions from different ecosystems."""
    result = await mcp_client.call_tool(
        name="get_latest_package_versions",
        arguments={
            "packages": [
                PackageVersionRequest(ecosystem=ecosystem, package_name=package_name)
            ]
        }
    )

    assert result.structured_content is not None
    response = GetLatestVersionsResponse.model_validate(result.structured_content)
    assert len(response.result) == 1, f"Expected 1 result, got {len(response.result)}: {response.result}. Errors: {response.lookup_errors}"
    assert response.result[0].ecosystem is ecosystem
    assert response.result[0].package_name == package_name
    assert "." in response.result[0].latest_version, (
        f"Expected version to contain '.', got {response.result[0].latest_version}"
    )

    minimum_expected_version_obj = Version(minimum_expected_version)
    latest_version = Version(response.result[0].latest_version)
    assert latest_version >= minimum_expected_version_obj, \
        f"Expected version >= {minimum_expected_version}, got {response.result[0].latest_version}"
    if minimum_expected_version_obj.variant:
        assert latest_version.variant == minimum_expected_version_obj.variant, \
            f"Expected variant '{minimum_expected_version_obj.variant}', got '{latest_version.variant}'"

    if ecosystem is Ecosystem.Docker:
        assert response.result[0].digest is not None
        assert response.result[0].digest.startswith("sha256:"), \
            f"Expected digest to start with 'sha256:', got {response.result[0].digest}"

    if ecosystem is Ecosystem.MavenGradle:
        # Maven/Gradle doesn't provide digest or published_on
        assert response.result[0].digest is None
        assert response.result[0].published_on is None

    if ecosystem in (Ecosystem.Go, Ecosystem.Swift):
        assert response.result[0].published_on is not None
        assert response.result[0].digest is not None

    if ecosystem in (Ecosystem.PHP, Ecosystem.RubyGems, Ecosystem.Rust, Ecosystem.Dart):
        # PHP, RubyGems, Rust, and Dart packages should have published_on but no digest
        assert response.result[0].published_on is not None
        assert response.result[0].digest is None

    assert len(response.lookup_errors) == 0, f"Expected 0 errors, got {len(response.lookup_errors)}: {response.lookup_errors}"


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
    (Ecosystem.RubyGems, "nonexistent-gem-12345-definitely-does-not-exist"),
    (Ecosystem.Rust, "nonexistent-crate-12345-definitely-does-not-exist"),
    (Ecosystem.Swift, "https://github.com/nonexistent-user-12345/nonexistent-repo-12345.git"),
])
async def test_get_latest_package_versions_not_found(mcp_client: Client, ecosystem, package_name):
    """Test fetching non-existent packages from different ecosystems."""
    result = await mcp_client.call_tool(
        name="get_latest_package_versions",
        arguments={
            "packages": [
                PackageVersionRequest(ecosystem=ecosystem, package_name=package_name)
            ]
        }
    )

    assert result.structured_content is not None
    response = GetLatestVersionsResponse.model_validate(result.structured_content)
    assert len(response.result) == 0, \
        f"Expected 0 results, got {len(response.result)}: {response.result}. " \
        f"Errors: {response.lookup_errors}"
    assert len(response.lookup_errors) == 1, \
        f"Expected 1 error, got {len(response.lookup_errors)}: {response.lookup_errors}. " \
        f"Results: {response.result}"
    assert response.lookup_errors[0].ecosystem is ecosystem
    assert response.lookup_errors[0].package_name == package_name
    # Different registries return different errors (404 Not Found, 403 Forbidden, etc.)
    error_lower = response.lookup_errors[0].error.lower()
    assert "not found" in error_lower or "403" in error_lower or "forbidden" in error_lower


async def test_get_latest_package_versions_mixed_success_and_failure(mcp_client: Client):
    """Test get_latest_package_versions with both valid and invalid packages."""
    result = await mcp_client.call_tool(
        name="get_latest_package_versions",
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
    assert len(response.result) == 2, \
        f"Expected 2 results, got {len(response.result)}: {response.result}. " \
        f"Errors: {response.lookup_errors}"
    assert response.result[0].package_name == "express"
    assert response.result[0].ecosystem is Ecosystem.NPM
    assert response.result[1].package_name == "requests"
    assert response.result[1].ecosystem is Ecosystem.PyPI

    # Should have 2 errors
    assert len(response.lookup_errors) == 2, \
        f"Expected 2 errors, got {len(response.lookup_errors)}: {response.lookup_errors}"
    assert all("not found" in err.error.lower() for err in response.lookup_errors), \
        f"Expected all errors to contain 'not found', got errors: " \
        f"{[err.error for err in response.lookup_errors]}"


async def test_get_latest_package_versions_empty_input(mcp_client: Client):
    """Test get_latest_package_versions with empty input."""
    result = await mcp_client.call_tool(
        name="get_latest_package_versions",
        arguments={"packages": []}
    )

    assert result.structured_content is not None
    response = GetLatestVersionsResponse.model_validate(result.structured_content)
    assert len(response.result) == 0, \
        f"Expected 0 results, got {len(response.result)}: {response.result}. " \
        f"Errors: {response.lookup_errors}"
    assert len(response.lookup_errors) == 0, \
        f"Expected 0 errors, got {len(response.lookup_errors)}: {response.lookup_errors}"


async def test_get_latest_package_versions_multiple_packages(mcp_client: Client):
    """Test get_latest_package_versions with multiple valid packages."""
    result = await mcp_client.call_tool(
        name="get_latest_package_versions",
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
    assert len(response.result) == 4, \
        f"Expected 4 results, got {len(response.result)}: {response.result}. " \
        f"Errors: {response.lookup_errors}"
    assert len(response.lookup_errors) == 0, \
        f"Expected 0 errors, got {len(response.lookup_errors)}: {response.lookup_errors}"

    # Verify all packages are present
    package_names = {pkg.package_name for pkg in response.result}
    assert package_names == {"express", "react", "requests", "flask"}, f"Got package names: {package_names}"

    # Verify all have valid versions
    for pkg in response.result:
        assert pkg.latest_version != ""
        assert "." in pkg.latest_version, f"Version missing '.': {pkg.latest_version}"


@pytest.mark.parametrize("package_name,version_hint,expected_suffix", [
    ("index.docker.io/library/busybox", "1.36-musl", "musl"),
    ("index.docker.io/library/busybox", "1.36-glibc", "glibc"),
    ("index.docker.io/library/memcached", "1-bookworm", "bookworm"),
])
async def test_get_latest_package_versions_docker_with_tag_hint(
    mcp_client: Client, package_name, version_hint, expected_suffix
):
    """Test fetching Docker image versions with tag compatibility hint."""
    result = await mcp_client.call_tool(
        name="get_latest_package_versions",
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
    assert len(response.result) == 1, \
        f"Expected 1 result, got {len(response.result)}: {response.result}. " \
        f"Errors: {response.lookup_errors}"
    assert response.result[0].ecosystem is Ecosystem.Docker
    assert response.result[0].package_name == package_name
    assert "." in response.result[0].latest_version, \
        f"Version missing '.': {response.result[0].latest_version}"
    # The returned tag should have the same suffix
    assert expected_suffix in response.result[0].latest_version.lower(), \
        f"Expected '{expected_suffix}' in version: {response.result[0].latest_version}"
    # Should have a digest
    assert response.result[0].digest is not None
    assert response.result[0].digest.startswith("sha256:"), \
        f"Digest should start with 'sha256:': {response.result[0].digest}"
    assert len(response.lookup_errors) == 0, \
        f"Expected 0 errors, got {len(response.lookup_errors)}: {response.lookup_errors}"


async def test_cache_disabled_logic(mocker: MockerFixture):
    """Verify cache behavior when disabled (default)."""
    # Setup
    request = PackageVersionRequest(ecosystem=Ecosystem.PyPI, package_name="requests")
    expected_result = PackageVersionResult(
        ecosystem=Ecosystem.PyPI,
        package_name="requests",
        latest_version="2.31.0"
    )

    # Patch CACHE_ENABLED to be False
    mocker.patch("package_version_check_mcp.get_latest_package_versions_pkg.dispatcher.CACHE_ENABLED", False)
    mock_fetch = mocker.patch("package_version_check_mcp.get_latest_package_versions_pkg.dispatcher.fetch_pypi_version", new_callable=mocker.AsyncMock)
    mock_fetch.return_value = expected_result

    # Clear cache to be safe
    _version_cache.clear()

    # First call
    result1 = await fetch_package_version(request)
    assert result1 == expected_result
    assert mock_fetch.call_count == 1

    # Second call - should fetch again because cache is disabled
    result2 = await fetch_package_version(request)
    assert result2 == expected_result
    assert mock_fetch.call_count == 2

    # Verify cache is still empty
    assert not _version_cache


async def test_cache_enabled_logic(mocker: MockerFixture):
    """Verify cache behavior when enabled."""
    # Setup
    request = PackageVersionRequest(ecosystem=Ecosystem.PyPI, package_name="requests")
    expected_result = PackageVersionResult(
        ecosystem=Ecosystem.PyPI,
        package_name="requests",
        latest_version="2.31.0"
    )

    # Patch CACHE_ENABLED to be True
    mocker.patch("package_version_check_mcp.get_latest_package_versions_pkg.dispatcher.CACHE_ENABLED", True)
    mock_fetch = mocker.patch("package_version_check_mcp.get_latest_package_versions_pkg.dispatcher.fetch_pypi_version", new_callable=mocker.AsyncMock)
    mock_fetch.return_value = expected_result

    # Clear cache
    _version_cache.clear()

    # First call
    result1 = await fetch_package_version(request)
    assert result1 == expected_result
    assert mock_fetch.call_count == 1

    # Second call - should hit cache
    result2 = await fetch_package_version(request)
    assert result2 == expected_result
    assert mock_fetch.call_count == 1

    # Verify in cache
    cache_key = (request.ecosystem, request.package_name, request.version_hint)
    assert cache_key in _version_cache

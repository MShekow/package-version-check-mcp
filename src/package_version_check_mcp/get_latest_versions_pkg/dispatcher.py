"""Main dispatcher for fetching package versions across different ecosystems."""

import httpx

from .structs import PackageVersionResult, PackageVersionRequest, PackageVersionError, Ecosystem
from .fetchers import (
    fetch_npm_version,
    fetch_pypi_version,
    fetch_nuget_version,
    fetch_maven_gradle_version,
    fetch_docker_version,
    fetch_helm_chart_version,
    fetch_terraform_provider_version,
    fetch_terraform_module_version,
    fetch_go_version,
    fetch_php_version,
)


async def fetch_package_version(
    request: PackageVersionRequest,
) -> PackageVersionResult | PackageVersionError:
    """Fetch the latest version of a package from its ecosystem.

    Args:
        request: The package version request

    Returns:
        Either a PackageVersionResult on success or PackageVersionError on failure
    """
    try:
        if request.ecosystem == Ecosystem.NPM:
            return await fetch_npm_version(request.package_name)
        elif request.ecosystem == Ecosystem.Docker:
            return await fetch_docker_version(request.package_name, request.version_hint)
        elif request.ecosystem == Ecosystem.NuGet:
            return await fetch_nuget_version(request.package_name)
        elif request.ecosystem == Ecosystem.MavenGradle:
            return await fetch_maven_gradle_version(request.package_name)
        elif request.ecosystem == Ecosystem.Helm:
            return await fetch_helm_chart_version(request.package_name, request.version_hint)
        elif request.ecosystem == Ecosystem.TerraformProvider:
            return await fetch_terraform_provider_version(request.package_name)
        elif request.ecosystem == Ecosystem.TerraformModule:
            return await fetch_terraform_module_version(request.package_name)
        elif request.ecosystem == Ecosystem.Go:
            return await fetch_go_version(request.package_name)
        elif request.ecosystem == Ecosystem.PHP:
            return await fetch_php_version(request.package_name, request.version_hint)
        else:  # Ecosystem.PyPI:
            return await fetch_pypi_version(request.package_name)
    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP error {e.response.status_code}: {e.response.reason_phrase}"
        if e.response.status_code == 404:
            error_msg = f"Package '{request.package_name}' not found"
        return PackageVersionError(
            ecosystem=request.ecosystem,
            package_name=request.package_name,
            error=error_msg,
        )
    except Exception as e:
        return PackageVersionError(
            ecosystem=request.ecosystem,
            package_name=request.package_name,
            error=f"Failed to fetch package version: {str(e)}",
        )

"""Main dispatcher for fetching package versions across different ecosystems."""

import os

import httpx
from cachetools import TTLCache

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
    fetch_rubygems_version,
    fetch_rust_version,
    fetch_swift_version,
    fetch_dart_version,
)
from .structs import PackageVersionResult, PackageVersionRequest, PackageVersionError, Ecosystem

# Cache configuration
# Default: Disabled
CACHE_ENABLED = os.environ.get("PACKAGE_VERSION_CACHE_ENABLED", "false").lower() == "true"
# Default TTL: 1 hour (3600 seconds)
CACHE_TTL = int(os.environ.get("PACKAGE_VERSION_CACHE_TTL_SECONDS", 3600))
# Default Max Size: 64 MB
CACHE_MAX_SIZE_MB = int(os.environ.get("PACKAGE_VERSION_CACHE_MAX_SIZE_MB", 64))
CACHE_MAX_SIZE_BYTES = CACHE_MAX_SIZE_MB * 1024 * 1024


def _get_sizeof(item) -> int:
    """Estimate the size of an item in bytes."""
    # Approximate memory size as 10x JSON size to account for Python object overhead
    if hasattr(item, "model_dump_json"):
        return len(item.model_dump_json()) * 10
    return 1024  # Fallback size for unknown objects


_version_cache = TTLCache(
    maxsize=CACHE_MAX_SIZE_BYTES,
    ttl=CACHE_TTL,
    getsizeof=_get_sizeof
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
    cache_key = (request.ecosystem, request.package_name, request.version_hint)

    if CACHE_ENABLED and cache_key in _version_cache:
        return _version_cache[cache_key]

    try:
        if request.ecosystem == Ecosystem.NPM:
            result = await fetch_npm_version(request.package_name)
        elif request.ecosystem == Ecosystem.Docker:
            result = await fetch_docker_version(request.package_name, request.version_hint)
        elif request.ecosystem == Ecosystem.NuGet:
            result = await fetch_nuget_version(request.package_name)
        elif request.ecosystem == Ecosystem.MavenGradle:
            result = await fetch_maven_gradle_version(request.package_name)
        elif request.ecosystem == Ecosystem.Helm:
            result = await fetch_helm_chart_version(request.package_name, request.version_hint)
        elif request.ecosystem == Ecosystem.TerraformProvider:
            result = await fetch_terraform_provider_version(request.package_name)
        elif request.ecosystem == Ecosystem.TerraformModule:
            result = await fetch_terraform_module_version(request.package_name)
        elif request.ecosystem == Ecosystem.Go:
            result = await fetch_go_version(request.package_name)
        elif request.ecosystem == Ecosystem.PHP:
            result = await fetch_php_version(request.package_name)
        elif request.ecosystem == Ecosystem.RubyGems:
            result = await fetch_rubygems_version(request.package_name)
        elif request.ecosystem == Ecosystem.Rust:
            result = await fetch_rust_version(request.package_name)
        elif request.ecosystem == Ecosystem.Swift:
            result = await fetch_swift_version(request.package_name)
        elif request.ecosystem == Ecosystem.Dart:
            result = await fetch_dart_version(request.package_name)
        else:  # Ecosystem.PyPI:
            result = await fetch_pypi_version(request.package_name)

        if CACHE_ENABLED:
            _version_cache[cache_key] = result
        return result

    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP error {e.response.status_code}: {e.response.reason_phrase}"
        if e.response.status_code == 404:
            error_msg = f"Package '{request.package_name}' not found"
        result = PackageVersionError(
            ecosystem=request.ecosystem,
            package_name=request.package_name,
            error=error_msg,
        )
        if CACHE_ENABLED:
            _version_cache[cache_key] = result
        return result
    except Exception as e:
        result = PackageVersionError(
            ecosystem=request.ecosystem,
            package_name=request.package_name,
            error=f"Failed to fetch package version: {str(e)}",
        )
        if CACHE_ENABLED:
            _version_cache[cache_key] = result
        return result

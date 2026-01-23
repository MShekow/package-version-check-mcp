"""Package Version Check MCP Server.

A FastMCP server that checks the latest versions of packages across different ecosystems.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

import httpx
from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

# Initialize the FastMCP server
mcp = FastMCP("Package Version Check")


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint for monitoring and load balancers."""
    return JSONResponse({"status": "healthy", "service": "package-version-check-mcp"})


class Ecosystem(str, Enum):
    """Supported package ecosystems."""

    NPM = "npm"
    PYPI = "pypi"


@dataclass
class PackageVersionRequest:
    """Request for a package version lookup."""

    ecosystem: Ecosystem
    package_name: str
    version: Optional[str] = None


@dataclass
class PackageVersionResult:
    """Successful package version lookup result."""

    ecosystem: str
    package_name: str
    latest_version: str
    digest: Optional[str] = None
    published_on: Optional[str] = None


@dataclass
class PackageVersionError:
    """Error during package version lookup."""

    ecosystem: str
    package_name: str
    error: str


@dataclass
class GetLatestVersionsResponse:
    """Response from get_latest_versions tool."""

    result: list[PackageVersionResult]
    lookup_errors: list[PackageVersionError]


async def fetch_npm_version(package_name: str) -> PackageVersionResult:
    """Fetch the latest version of an NPM package.

    Args:
        package_name: The name of the NPM package

    Returns:
        PackageVersionResult with the latest version information

    Raises:
        Exception: If the package cannot be found or fetched
    """
    url = f"https://registry.npmjs.org/{package_name}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()

        # Get the latest version from dist-tags
        version = data.get("dist-tags", {}).get("latest", "ERROR")

        # Get the publication time for this version
        published_on = None
        if "time" in data and version in data["time"]:
            published_on = data["time"][version]

        return PackageVersionResult(
            ecosystem="npm",
            package_name=package_name,
            latest_version=version,
            digest=None,  # NPM doesn't provide digest in the same way
            published_on=published_on,
        )


async def fetch_pypi_version(package_name: str) -> PackageVersionResult:
    """Fetch the latest version of a PyPI package.

    Args:
        package_name: The name of the PyPI package

    Returns:
        PackageVersionResult with the latest version information

    Raises:
        Exception: If the package cannot be found or fetched
    """
    url = f"https://pypi.org/pypi/{package_name}/json"

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()

        info = data.get("info", {})
        version = info.get("version", "ERROR")

        # Get the upload time for the latest version
        published_on = None
        releases = data.get("releases", {})
        if version in releases and releases[version]:
            # Get the first release file's upload time
            upload_time = releases[version][0].get("upload_time_iso_8601")
            if upload_time:
                published_on = upload_time

        # PyPI provides digests for individual files, not the package as a whole
        # We could return the digest of the first wheel/source dist if needed
        digest = None
        if version in releases and releases[version]:
            # Get the sha256 digest of the first file
            first_file = releases[version][0]
            if "digests" in first_file and "sha256" in first_file["digests"]:
                digest = f"sha256:{first_file['digests']['sha256']}"

        return PackageVersionResult(
            ecosystem="pypi",
            package_name=package_name,
            latest_version=version,
            digest=digest,
            published_on=published_on,
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
        else: # Ecosystem.PYPI:
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


@mcp.tool()
async def get_latest_versions(
    packages: list[PackageVersionRequest],
) -> GetLatestVersionsResponse:
    """Get the latest versions of packages from various ecosystems.

    This tool fetches the latest version information for packages from NPM and PyPI.
    It returns both successful lookups and any errors that occurred.

    Args:
        packages: A list of package version requests with:
            - ecosystem: "npm" or "pypi"
            - package_name: The name of the package (e.g., "express", "requests")
            - version: (optional) A version constraint (currently not used for filtering)

    Returns:
        GetLatestVersionsResponse containing:
            - result: List of successful package version lookups with:
                - ecosystem: The package ecosystem (as provided)
                - package_name: The package name (as provided)
                - latest_version: The latest version number (e.g., "1.2.4")
                - digest: (optional) Package digest/hash if available
                - published_on: (optional) Publication date if available
            - lookup_errors: List of errors that occurred during lookup with:
                - ecosystem: The package ecosystem (as provided)
                - package_name: The package name (as provided)
                - error: Description of the error

    Example:
        >>> await get_latest_versions([
        ...     PackageVersionRequest(ecosystem=Ecosystem.NPM, package_name="express"),
        ...     PackageVersionRequest(ecosystem=Ecosystem.PYPI, package_name="requests")
        ... ])
    """
    # Fetch all package versions concurrently
    results = await asyncio.gather(
        *[fetch_package_version(req) for req in packages],
        return_exceptions=False,
    )

    # Separate successful results from errors
    successful_results = []
    errors = []

    for result in results:
        if isinstance(result, PackageVersionResult):
            successful_results.append(result)
        elif isinstance(result, PackageVersionError):
            errors.append(result)

    return GetLatestVersionsResponse(result=successful_results, lookup_errors=errors)


def main():
    """Main entry point for the MCP server."""
    mcp.run(transport="sse")


if __name__ == "__main__":
    main()

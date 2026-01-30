"""Package Version Check MCP Server.

A FastMCP server that checks the latest versions of packages across different ecosystems.
"""

import argparse
import asyncio

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from package_version_check_mcp.get_github_actions_pkg.functions import fetch_github_action
from package_version_check_mcp.get_github_actions_pkg.structs import GitHubActionResult, GitHubActionError, \
    GetGitHubActionVersionsResponse
from package_version_check_mcp.get_latest_versions_pkg.functions import fetch_package_version
from package_version_check_mcp.get_latest_versions_pkg.structs import Ecosystem, PackageVersionRequest, \
    PackageVersionResult, PackageVersionError, GetLatestVersionsResponse

mcp = FastMCP("Package Version Check")


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint for monitoring and load balancers."""
    return JSONResponse({"status": "healthy", "service": "package-version-check-mcp"})


@mcp.tool()
async def get_latest_versions(
    packages: list[PackageVersionRequest],
) -> GetLatestVersionsResponse:
    """Get the latest versions of packages from various ecosystems.

    This tool fetches the latest version information for packages from NPM, PyPI, Docker, NuGet, Maven/Gradle, and Helm.
    It returns both successful lookups and any errors that occurred.

    Args:
        packages: A list of package version requests with:
            - ecosystem: "npm", "pypi", "docker", "nuget", "maven_gradle", or "helm"
            - package_name: The name of the package (e.g., "express", "requests", "Newtonsoft.Json")
              For Docker, this must be fully qualified (e.g., "index.docker.io/library/busybox")
              For Maven/Gradle, use format "[registry:]<groupId>:<artifactId>" (e.g., "org.springframework:spring-core" for Maven Central,
              "maven.google.com:com.google.android.material:material" for Google Maven)
              For Helm, use one of these formats:
                - ChartMuseum: "https://host/path/chart-name" (fetches from index.yaml)
                - OCI: "oci://host/path/chart-name" (queries OCI registry tags)
            - version: (optional) For Docker and Helm OCI, used as a tag compatibility hint (e.g., "1.2-alpine")
              to find the latest tag matching the same suffix pattern. For NPM/PyPI/NuGet/Maven/ChartMuseum, not used.

    Returns:
        GetLatestVersionsResponse containing:
            - result: List of successful package version lookups with:
                - ecosystem: The package ecosystem (as provided)
                - package_name: The package name (as provided)
                - latest_version: The latest version number (e.g., "1.2.4") or Docker tag
                - digest: (optional) Package digest/hash if available
                - published_on: (optional) Publication date if available
            - lookup_errors: List of errors that occurred during lookup with:
                - ecosystem: The package ecosystem (as provided)
                - package_name: The package name (as provided)
                - error: Description of the error

    Example:
        >>> await get_latest_versions([
        ...     PackageVersionRequest(ecosystem=Ecosystem.NPM, package_name="express"),
        ...     PackageVersionRequest(ecosystem=Ecosystem.PyPI, package_name="requests"),
        ...     PackageVersionRequest(ecosystem=Ecosystem.NuGet, package_name="Newtonsoft.Json"),
        ...     PackageVersionRequest(ecosystem=Ecosystem.MavenGradle, package_name="org.springframework:spring-core"),
        ...     PackageVersionRequest(ecosystem=Ecosystem.Docker, package_name="index.docker.io/library/alpine", version="3.19-alpine"),
        ...     PackageVersionRequest(ecosystem=Ecosystem.Helm, package_name="https://charts.bitnami.com/bitnami/nginx"),
        ...     PackageVersionRequest(ecosystem=Ecosystem.Helm, package_name="oci://ghcr.io/argoproj/argo-helm/argo-cd"),
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


@mcp.tool()
async def get_github_action_versions_and_args(
    action_names: list[str], include_readme: bool = False
) -> GetGitHubActionVersionsResponse:
    """Get the latest versions and metadata for GitHub Actions.

    This tool fetches the latest Git tag and action.yml metadata for GitHub Actions
    hosted on github.com. It can optionally include the README.md for usage instructions.

    Args:
        action_names: A list of action names in "owner/repo" format
            (e.g., ["actions/checkout", "docker/login-action"])
        include_readme: Whether to include the README.md content (default: False)

    Returns:
        GetGitHubActionVersionsResponse containing:
            - result: List of successful action lookups with:
                - name: The action name (as provided)
                - latest_version: The most recent Git tag (e.g., "v3.2.4")
                - digest: The commit SHA that the tag points to
                - metadata: The action.yml fields (inputs, outputs, runs) as a dict
                - readme: (optional) The README content if include_readme was True
            - lookup_errors: List of errors that occurred during lookup with:
                - name: The action name (as provided)
                - error: Description of the error

    Example:
        >>> await get_github_action_versions_and_args(
        ...     action_names=["actions/checkout", "docker/login-action"],
        ...     include_readme=True
        ... )
    """
    # Fetch all action information concurrently
    results = await asyncio.gather(
        *[fetch_github_action(name, include_readme) for name in action_names],
        return_exceptions=False,
    )

    # Separate successful results from errors
    successful_results = []
    errors = []

    for result in results:
        if isinstance(result, GitHubActionResult):
            successful_results.append(result)
        elif isinstance(result, GitHubActionError):
            errors.append(result)

    return GetGitHubActionVersionsResponse(result=successful_results, lookup_errors=errors)


def main():
    """Main entry point for the MCP server."""
    parser = argparse.ArgumentParser(description="Package Version Check MCP Server")
    parser.add_argument(
        "--mode",
        choices=["http", "stdio"],
        default="stdio",
        help="Transport mode: 'http' for HTTP server, 'stdio' for stdio transport (default: stdio)"
    )
    args = parser.parse_args()

    if args.mode == "http":
        mcp.run(transport="http", host="0.0.0.0", port=8000)
    else:
        mcp.run()


if __name__ == "__main__":
    main()

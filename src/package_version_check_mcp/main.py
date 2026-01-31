"""Package Version Check MCP Server.

A FastMCP server that checks the latest versions of packages across different ecosystems.
"""

import argparse
import asyncio
import json
import subprocess

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from package_version_check_mcp.get_github_actions_pkg.functions import fetch_github_action
from package_version_check_mcp.get_github_actions_pkg.structs import GitHubActionResult, GitHubActionError, \
    GetGitHubActionVersionsResponse
from package_version_check_mcp.get_latest_versions_pkg import fetch_package_version
from package_version_check_mcp.get_latest_versions_pkg.structs import PackageVersionRequest, \
    PackageVersionResult, PackageVersionError, GetLatestVersionsResponse
from package_version_check_mcp.get_latest_tools_pkg.functions import fetch_latest_tool_version
from package_version_check_mcp.get_latest_tools_pkg.structs import LatestToolResult, LatestToolError, \
    GetLatestToolVersionsResponse

mcp = FastMCP("Package Version Check")


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint for monitoring and load balancers."""
    return JSONResponse({"status": "healthy", "service": "package-version-check-mcp"})


@mcp.tool()
async def get_latest_package_versions(
    packages: list[PackageVersionRequest],
) -> GetLatestVersionsResponse:
    """Get the latest versions of packages from various ecosystems.

    This tool fetches the latest version information for packages from NPM, PyPI, Docker, NuGet, Maven/Gradle, Helm, Go modules, and PHP/Packagist.
    It returns both successful lookups and any errors that occurred.

    Args:
        packages: A list of package version requests with:
            - ecosystem: "npm", "pypi", "docker", "nuget", "maven_gradle", "helm", "terraform_provider", "terraform_module", "go", or "php"
            - package_name: The name of the package (e.g., "express", "requests", "Newtonsoft.Json")
              For Docker, this must be fully qualified (e.g., "index.docker.io/library/busybox")
              For Maven/Gradle, use format "[registry:]<groupId>:<artifactId>" (e.g., "org.springframework:spring-core" for Maven Central,
              "maven.google.com:com.google.android.material:material" for Google Maven)
              For Helm, use one of these formats:
                - ChartMuseum: "https://host/path/chart-name" (fetches from index.yaml)
                - OCI: "oci://host/path/chart-name" (queries OCI registry tags)
              For Go, use the absolute module identifier (e.g., "github.com/gin-gonic/gin")
              For PHP, use the Packagist package name in "vendor/package" format (e.g., "monolog/monolog", "laravel/framework")
            - version_hint: (optional) For Docker and Helm OCI, used as a tag compatibility hint (e.g., "1.2-alpine")
              to find the latest tag matching the same suffix pattern.
              For PHP, used as a PHP version hint (e.g., "php:8.1") to filter packages compatible with that PHP version.
              For NPM/PyPI/NuGet/Maven/ChartMuseum/Go, not used.

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
        >>> await get_latest_package_versions([
        ...     PackageVersionRequest(ecosystem=Ecosystem.NPM, package_name="express"),
        ...     PackageVersionRequest(ecosystem=Ecosystem.PyPI, package_name="requests"),
        ...     PackageVersionRequest(ecosystem=Ecosystem.NuGet, package_name="Newtonsoft.Json"),
        ...     PackageVersionRequest(ecosystem=Ecosystem.MavenGradle, package_name="org.springframework:spring-core"),
        ...     PackageVersionRequest(ecosystem=Ecosystem.Docker, package_name="index.docker.io/library/alpine", version_hint="3.19-alpine"),
        ...     PackageVersionRequest(ecosystem=Ecosystem.Helm, package_name="https://charts.bitnami.com/bitnami/nginx"),
        ...     PackageVersionRequest(ecosystem=Ecosystem.Helm, package_name="oci://ghcr.io/argoproj/argo-helm/argo-cd"),
        ...     PackageVersionRequest(ecosystem=Ecosystem.Go, package_name="github.com/gin-gonic/gin"),
        ...     PackageVersionRequest(ecosystem=Ecosystem.PHP, package_name="monolog/monolog"),
        ...     PackageVersionRequest(ecosystem=Ecosystem.PHP, package_name="laravel/framework", version_hint="php:8.1"),
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


@mcp.tool()
async def get_supported_tools() -> list[str]:
    """Get list of all tools supported by the get_latest_tool_versions MCP tool.

    This tool queries the mise registry to retrieve all available tool names
    that can be used with the get_latest_tool_versions tool.

    Returns:
        A list of tool short names (e.g., ["1password", "act", "node", "python", ...])

    Example:
        >>> await get_supported_tools()
        ["1password", "act", "node", "python", ...]
    """
    result = subprocess.run(
        ["mise", "registry", "--json"],
        capture_output=True,
        text=True,
        check=True,
    )
    registry = json.loads(result.stdout)
    return [entry["short"] for entry in registry]


@mcp.tool()
async def get_latest_tool_versions(
    tool_names: list[str],
) -> GetLatestToolVersionsResponse:
    """Get the latest stable versions of tools supported by mise-en-place.

    This tool fetches the latest stable version of development and DevOps tools
    that are NOT part of language ecosystems like PyPI or NPM. For language
    ecosystem packages, use the get_latest_package_versions tool instead.

    Use this tool to determine the latest versions of tools like:
    - gradle: Pin the Gradle version in distributionUrl in gradle-wrapper.properties
      (e.g., distributionUrl=https://services.gradle.org/distributions/gradle-8.5-bin.zip)
    - maven: Pin the Maven version in distributionUrl in maven-wrapper.properties
      (e.g., distributionUrl=https://repo.maven.apache.org/maven2/org/apache/maven/apache-maven/3.9.6/apache-maven-3.9.6-bin.zip)
    - terraform: Pin terraform.required_version in a file like version.tf or versions.tf
      (e.g., terraform { required_version = "~> 1.6.0" })
    - kubectl: Pin the version in a download URL called with curl or wget in a Dockerfile
      (e.g., RUN curl -LO https://dl.k8s.io/release/v1.28.0/bin/linux/amd64/kubectl)
    - azure: Pin Azure CLI version in download URL
      (e.g., curl -LO https://azurecliprod.blob.core.windows.net/releases/azure-cli-2.50.0.tar.gz)

    To see all available tools, use the get_supported_tools tool.

    Args:
        tool_names: A list of tool names (e.g., ["terraform", "gradle", "kubectl"])

    Returns:
        GetMiseToolVersionsResponse containing:
            - result: List of successful tool version lookups with:
                - tool_name: The tool name (as provided)
                - latest_version: The latest stable version number (e.g., "1.6.5")
            - lookup_errors: List of errors that occurred during lookup with:
                - tool_name: The tool name (as provided)
                - error: Description of the error

    Example:
        >>> await get_latest_tool_versions(
        ...     tool_names=["terraform", "gradle", "kubectl"]
        ... )
    """
    # Fetch all tool versions concurrently
    results = await asyncio.gather(
        *[fetch_latest_tool_version(name) for name in tool_names],
        return_exceptions=False,
    )

    # Separate successful results from errors
    successful_results = []
    errors = []

    for result in results:
        if isinstance(result, LatestToolResult):
            successful_results.append(result)
        elif isinstance(result, LatestToolError):
            errors.append(result)

    return GetLatestToolVersionsResponse(result=successful_results, lookup_errors=errors)


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

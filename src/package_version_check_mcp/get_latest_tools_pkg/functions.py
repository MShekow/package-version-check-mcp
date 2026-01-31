"""Functions for fetching latest versions of mise-supported tools."""

import json
import subprocess
from typing import Union

from package_version_check_mcp.get_latest_versions_pkg.utils.version_parser import parse_semver, compare_semver
from .structs import LatestToolResult, LatestToolError


def is_stable_version(version: str) -> bool:
    """Check if a version is a stable release (not a prerelease).

    Args:
        version: The version string to check

    Returns:
        True if the version is stable (no prerelease suffix), False otherwise
    """
    _, prerelease = parse_semver(version)
    # A version is stable if it has no prerelease suffix
    return not prerelease


def is_numeric_version(version: str) -> bool:
    """Check if a version starts with a digit (e.g., "1.2.3" or "23.0.1").

    Filters out vendor-specific versions like "zulu-8.72.0.17".

    Args:
        version: The version string to check

    Returns:
        True if the version starts with a digit, False otherwise
    """
    return bool(version and version[0].isdigit())


async def fetch_latest_tool_version(tool_name: str) -> Union[LatestToolResult, LatestToolError]:
    """Fetch the latest stable version of a mise-supported tool.

    Args:
        tool_name: The name of the tool (e.g., "terraform", "gradle", "kubectl")

    Returns:
        LatestToolResult if successful, LatestToolError if an error occurred
    """
    try:
        # Run mise ls-remote command to get all versions
        result = subprocess.run(
            ["mise", "ls-remote", tool_name, "--json"],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )

        versions_data = json.loads(result.stdout)

        if not versions_data:
            return LatestToolError(
                tool_name=tool_name,
                error=f"No versions found for tool '{tool_name}'"
            )

        # Filter to only numeric versions (exclude vendor-specific ones like "zulu-X.X.X")
        numeric_versions = [
            entry["version"]
            for entry in versions_data
            if is_numeric_version(entry["version"])
        ]

        if not numeric_versions:
            return LatestToolError(
                tool_name=tool_name,
                error=f"No numeric versions found for tool '{tool_name}'"
            )

        # Filter to only stable versions (no prerelease suffixes)
        stable_versions = [
            version
            for version in numeric_versions
            if is_stable_version(version)
        ]

        # If no stable versions found, fall back to all numeric versions
        versions_to_check = stable_versions if stable_versions else numeric_versions

        # Find the latest version (mise output is already sorted, so take the last one)
        # But to be safe, let's find the max using semver comparison
        latest_version = versions_to_check[0]
        for version in versions_to_check[1:]:
            if compare_semver(version, latest_version) > 0:
                latest_version = version

        return LatestToolResult(
            tool_name=tool_name,
            latest_version=latest_version
        )

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() if e.stderr else str(e)
        return LatestToolError(
            tool_name=tool_name,
            error=f"Failed to fetch versions for '{tool_name}': {error_msg}"
        )
    except subprocess.TimeoutExpired:
        return LatestToolError(
            tool_name=tool_name,
            error=f"Timeout while fetching versions for '{tool_name}'"
        )
    except json.JSONDecodeError as e:
        return LatestToolError(
            tool_name=tool_name,
            error=f"Failed to parse JSON output for '{tool_name}': {str(e)}"
        )
    except Exception as e:
        return LatestToolError(
            tool_name=tool_name,
            error=f"Unexpected error fetching versions for '{tool_name}': {str(e)}"
        )

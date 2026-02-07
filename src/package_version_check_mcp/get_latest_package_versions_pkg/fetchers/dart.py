"""Dart package version fetcher."""

import httpx

from ..structs import PackageVersionResult, Ecosystem


async def fetch_dart_version(package_name: str) -> PackageVersionResult:
    """Fetch the latest version of a Dart package from pub.dev.

    Args:
        package_name: The name of the Dart package on pub.dev

    Returns:
        PackageVersionResult with the latest version information

    Raises:
        Exception: If the package cannot be found or fetched
    """
    url = f"https://pub.dev/api/packages/{package_name}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()

        # Get the latest version info
        latest = data.get("latest", {})
        version = latest.get("version")

        if not version:
            raise ValueError(f"No version found for Dart package '{package_name}'")

        # Get the published date from the latest version
        published_on = latest.get("published")

        return PackageVersionResult(
            ecosystem=Ecosystem.Dart,
            package_name=package_name,
            latest_version=version,
            digest=None,  # Not including digest as requested
            published_on=published_on,
        )

"""RubyGems package version fetcher."""

import httpx

from ..structs import PackageVersionResult, Ecosystem


async def fetch_rubygems_version(package_name: str) -> PackageVersionResult:
    """Fetch the latest stable version of a RubyGems package.

    Args:
        package_name: The name of the RubyGems package

    Returns:
        PackageVersionResult with the latest version information

    Raises:
        Exception: If the package cannot be found or fetched
    """
    url = f"https://rubygems.org/api/v1/versions/{package_name}.json"

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        versions = response.json()

        # Filter for stable versions only (no prerelease)
        stable_versions = [v for v in versions if not v.get("prerelease", False)]

        if not stable_versions:
            raise ValueError(f"No stable versions found for gem '{package_name}'")

        # Versions are returned in descending order, so first is latest
        latest = stable_versions[0]

        return PackageVersionResult(
            ecosystem=Ecosystem.RubyGems,
            package_name=package_name,
            latest_version=latest["number"],
            digest=None,  # Not including digest as devs don't pin by digest anyway
            published_on=latest.get("created_at"),
        )

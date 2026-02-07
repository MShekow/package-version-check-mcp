"""NPM package version fetcher."""

import httpx

from ..structs import PackageVersionResult, Ecosystem


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
            ecosystem=Ecosystem.NPM,
            package_name=package_name,
            latest_version=version,
            digest=None,  # NPM doesn't provide digest in the same way
            published_on=published_on,
        )

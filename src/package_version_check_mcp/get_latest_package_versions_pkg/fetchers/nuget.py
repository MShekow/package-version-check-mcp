"""NuGet package version fetcher."""

import httpx

from ..structs import PackageVersionResult, Ecosystem
from ...utils.version_parser import Version, InvalidVersion


async def fetch_nuget_version(package_name: str) -> PackageVersionResult:
    """Fetch the latest stable version of a NuGet package.

    Args:
        package_name: The name of the NuGet package

    Returns:
        PackageVersionResult with the latest version information

    Raises:
        Exception: If the package cannot be found or fetched
    """
    # NuGet V3 API - Use the registration API
    registrations_url = "https://api.nuget.org/v3/registration5-semver1/"
    package_url = f"{registrations_url}{package_name.lower()}/index.json"

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(package_url)
        response.raise_for_status()
        package_data = response.json()

        # Extract all versions
        stable_versions = []
        items = package_data.get("items", [])
        for page in items:
            page_items = page.get("items", [])
            for item in page_items:
                catalog_entry = item.get("catalogEntry", {})
                version_str = catalog_entry.get("version")
                published = catalog_entry.get("published")

                if version_str:
                    try:
                        parsed_version = Version(version_str)
                        # Filter out prerelease versions
                        if not parsed_version.is_prerelease:
                            stable_versions.append({
                                "version": parsed_version,
                                "published": published
                            })
                    except InvalidVersion:
                        # Skip versions that can't be parsed
                        continue

        if not stable_versions:
            raise Exception(f"No stable versions found for package '{package_name}'")

        # Get the latest stable version
        latest = max(stable_versions, key=lambda v: v["version"])

        return PackageVersionResult(
            ecosystem=Ecosystem.NuGet,
            package_name=package_name,
            latest_version=str(latest["version"]),
            digest=None,  # NuGet doesn't provide digest in the registration API
            published_on=latest["published"] if latest["published"] != "1900-01-01T00:00:00+00:00" else None,
        )

"""PHP/Packagist package version fetcher using the Packagist v2 API."""

import httpx

from ..structs import PackageVersionResult, Ecosystem
from ...utils.version_parser import Version, InvalidVersion


async def fetch_php_version(package_name: str) -> PackageVersionResult:
    """Fetch the latest stable version of a PHP/Packagist package.

    Uses the Packagist v2 API (repo.packagist.org/p2/) which returns
    minified package metadata.

    Args:
        package_name: The package name in 'vendor/package' format (e.g., 'monolog/monolog')

    Returns:
        PackageVersionResult with the latest stable version information

    Raises:
        Exception: If the package cannot be found or fetched
    """
    # Normalize package name (should be vendor/package)
    if "/" not in package_name:
        raise ValueError(
            f"Invalid PHP package name '{package_name}'. "
            "Expected format: 'vendor/package' (e.g., 'monolog/monolog')"
        )

    url = f"https://repo.packagist.org/p2/{package_name}.json"

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            url,
            headers={
                "User-Agent": "package-version-check-mcp/1.0"
            },
        )
        response.raise_for_status()
        data = response.json()

        packages = data.get("packages", {})
        versions_list = packages.get(package_name, [])

        if not versions_list:
            raise ValueError(f"No versions found for package '{package_name}'")

        # The v2 API returns versions in a minified format.
        # The first entry has full data, subsequent entries only have changed fields.
        # We need to "expand" the data by carrying forward unchanged fields.
        # For our purposes, we mainly care about version, time, and require.php

        latest_version = None
        latest_time = None

        # Track the "current" full record as we iterate
        current_record = {}

        for version_data in versions_list:
            # Merge with current record (version_data overrides)
            current_record = {**current_record, **version_data}

            version = current_record.get("version", "")

            # Skip non-stable versions (those with prerelease suffix)
            try:
                # Basic check for prerelease property
                if Version(version).is_prerelease:
                    continue
            except InvalidVersion:
                # Skip invalid versions
                continue

            # Take the first stable version that matches (they're ordered newest first)
            latest_version = version
            latest_time = current_record.get("time")
            break

        if not latest_version:
            raise ValueError(f"No stable version found for package '{package_name}'")

        return PackageVersionResult(
            ecosystem=Ecosystem.PHP,
            package_name=package_name,
            latest_version=latest_version,
            digest=None,  # Not returning digest as per requirements
            published_on=latest_time,
        )

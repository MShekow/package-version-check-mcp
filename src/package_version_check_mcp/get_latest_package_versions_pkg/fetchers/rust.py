"""Rust/Crates.io package version fetcher."""

import httpx

from ..structs import PackageVersionResult, Ecosystem
from ...utils.version_parser import Version, InvalidVersion


async def fetch_rust_version(package_name: str) -> PackageVersionResult:
    """Fetch the latest stable version of a Rust crate from crates.io.

    Args:
        package_name: The name of the Rust crate

    Returns:
        PackageVersionResult with the latest version information

    Raises:
        Exception: If the package cannot be found or fetched
    """
    url = f"https://crates.io/api/v1/crates/{package_name}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()

        versions = data.get("versions", [])
        if not versions:
            raise ValueError(f"No versions found for crate '{package_name}'")

        # Parse all versions and separate stable from prerelease
        stable_versions = []
        prerelease_versions = []

        for version_data in versions:
            version_num = version_data.get("num", "")
            try:
                v = Version(version_num)
                if v.is_prerelease:
                    prerelease_versions.append(version_data)
                else:
                    stable_versions.append(version_data)
            except InvalidVersion:
                continue

        # Prefer stable versions, fall back to prereleases if no stable versions exist
        if stable_versions:
            latest = stable_versions[0]
        elif prerelease_versions:
            latest = prerelease_versions[0]
        else:
            raise ValueError(f"No parseable versions found for crate '{package_name}'")

        return PackageVersionResult(
            ecosystem=Ecosystem.Rust,
            package_name=package_name,
            latest_version=latest["num"],
            digest=None,  # Not including digest as per requirements
            published_on=latest.get("created_at"),
        )

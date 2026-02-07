"""PyPI package version fetcher."""

import httpx

from ..structs import PackageVersionResult, Ecosystem


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
            ecosystem=Ecosystem.PyPI,
            package_name=package_name,
            latest_version=version,
            digest=digest,
            published_on=published_on,
        )

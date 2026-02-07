"""Go module version fetcher."""

import httpx

from ..structs import PackageVersionResult, Ecosystem


async def fetch_go_version(package_name: str) -> PackageVersionResult:
    """Fetch the latest version of a Go module.

    Args:
        package_name: The name of the Go module e.g. "github.com/gin-gonic/gin"

    Returns:
        PackageVersionResult with the latest version information

    Raises:
        Exception: If the package cannot be found or fetched
    """
    url = f"https://proxy.golang.org/{package_name}/@latest"

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()

        version = data.get("Version")
        published_on = data.get("Time")

        # Try to get hash from Origin if available
        digest = None
        origin = data.get("Origin")
        if origin and isinstance(origin, dict):
            digest = origin.get("Hash")

        return PackageVersionResult(
            ecosystem=Ecosystem.Go,
            package_name=package_name,
            latest_version=version,
            digest=digest,
            published_on=published_on,
        )

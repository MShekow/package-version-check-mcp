"""Swift package version fetcher."""

from ..structs import PackageVersionResult, Ecosystem
from ..utils.github import fetch_latest_github_tag, create_github_client


async def fetch_swift_version(package_name: str) -> PackageVersionResult:
    """Fetch the latest version of a Swift package from GitHub.

    Args:
        package_name: The GitHub URL of the Swift package (e.g., "https://github.com/owner/repo.git")

    Returns:
        PackageVersionResult with the latest version information

    Raises:
        Exception: If the package cannot be found or fetched
    """
    # Parse the GitHub URL to extract owner and repo
    # Expected format: https://github.com/owner/repo.git or github.com/owner/repo.git
    package_name = package_name.strip()

    # Remove https:// or http:// prefix if present
    if package_name.startswith("https://"):
        package_name = package_name[8:]
    elif package_name.startswith("http://"):
        package_name = package_name[7:]

    # Verify it's a github.com URL
    if not package_name.startswith("github.com/"):
        raise ValueError(
            f"Invalid Swift package URL: '{package_name}'. Only github.com URLs are supported."
        )

    # Remove github.com/ prefix
    package_name = package_name[11:]

    # Remove .git suffix if present
    if package_name.endswith(".git"):
        package_name = package_name[:-4]

    # Split into owner and repo
    parts = package_name.split("/")
    if len(parts) != 2:
        raise ValueError(
            f"Invalid GitHub repository format: '{package_name}'. Expected 'owner/repo'"
        )

    owner, repo = parts

    async with create_github_client(timeout=10.0) as client:
        # Fetch the latest tag, its commit SHA, and commit date
        latest_tag, commit_sha, commit_date = await fetch_latest_github_tag(owner, repo, client)

        return PackageVersionResult(
            ecosystem=Ecosystem.Swift,
            package_name=f"https://github.com/{owner}/{repo}.git",
            latest_version=latest_tag,
            digest=commit_sha,
            published_on=commit_date,
        )

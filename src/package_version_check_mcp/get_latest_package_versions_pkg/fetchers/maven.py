"""Maven/Gradle package version fetcher."""

import xml.etree.ElementTree as ET

import httpx

from ..structs import PackageVersionResult, Ecosystem
from ...utils.version_parser import Version, InvalidVersion


def parse_maven_package_name(package_name: str) -> tuple[str, str, str]:
    """Parse a Maven/Gradle package name into registry, group ID, and artifact ID.

    Args:
        package_name: Package name in format "[registry:]<groupId>:<artifactId>"
                      If registry is omitted, Maven Central is assumed.

    Returns:
        A tuple of (registry_url, group_id, artifact_id)

    Raises:
        ValueError: If the package name format is invalid
    """
    # Handle URLs with protocol (http:// or https://)
    # These have an extra colon from the protocol
    if package_name.startswith("https://"):
        # Format: "https://host/path:groupId:artifactId"
        # After removing "https://", split by ":" to get host/path, groupId, artifactId
        rest = package_name[8:]  # Remove "https://"
        parts = rest.split(":")
        if len(parts) != 3:
            raise ValueError(
                f"Invalid Maven/Gradle package name format: '{package_name}'. "
                "Expected format: '[registry:]<groupId>:<artifactId>'"
            )
        registry = f"https://{parts[0]}".rstrip("/")
        group_id, artifact_id = parts[1], parts[2]
    elif package_name.startswith("http://"):
        # Format: "http://host/path:groupId:artifactId"
        rest = package_name[7:]  # Remove "http://"
        parts = rest.split(":")
        if len(parts) != 3:
            raise ValueError(
                f"Invalid Maven/Gradle package name format: '{package_name}'. "
                "Expected format: '[registry:]<groupId>:<artifactId>'"
            )
        registry = f"http://{parts[0]}".rstrip("/")
        group_id, artifact_id = parts[1], parts[2]
    else:
        # No protocol prefix
        parts = package_name.split(":")
        if len(parts) == 2:
            # No registry specified, use Maven Central
            registry = "https://repo1.maven.org/maven2"
            group_id, artifact_id = parts
        elif len(parts) == 3:
            # Registry specified without protocol
            registry = f"https://{parts[0]}".rstrip("/")
            group_id, artifact_id = parts[1], parts[2]
        else:
            raise ValueError(
                f"Invalid Maven/Gradle package name format: '{package_name}'. "
                "Expected format: '[registry:]<groupId>:<artifactId>'"
            )

    if not group_id or not artifact_id:
        raise ValueError(
            f"Invalid Maven/Gradle package name: '{package_name}'. "
            "Both groupId and artifactId must be non-empty."
        )

    return registry, group_id, artifact_id


async def fetch_maven_gradle_version(package_name: str) -> PackageVersionResult:
    """Fetch the latest version of a Maven/Gradle package.

    Args:
        package_name: Package name in format "[registry:]<groupId>:<artifactId>"
                      If registry is omitted, Maven Central is assumed.
                      Example: "org.springframework:spring-core" (Maven Central)
                      Example: "https://maven.google.com:com.google.android:android" (Google Maven)

    Returns:
        PackageVersionResult with the latest version information

    Raises:
        Exception: If the package cannot be found or fetched
    """
    registry, group_id, artifact_id = parse_maven_package_name(package_name)

    # Convert group ID to path format (e.g., "org.springframework" -> "org/springframework")
    group_path = group_id.replace(".", "/")

    # Construct maven-metadata.xml URL
    metadata_url = f"{registry}/{group_path}/{artifact_id}/maven-metadata.xml"

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(metadata_url)
        response.raise_for_status()

        # Parse the XML response
        root = ET.fromstring(response.text)

        # Look for <versioning><versions>...</versions></versioning>
        versioning = root.find("versioning")
        if versioning is None:
            raise Exception(f"No versioning information found for package '{package_name}'")

        versions_element = versioning.find("versions")
        if versions_element is None:
            raise Exception(f"No versions list found for package '{package_name}'")

        # Parse all version strings from <version> elements
        version_strings = [v.text for v in versions_element.findall("version") if v.text]
        if not version_strings:
            raise Exception(f"No versions found for package '{package_name}'")

        # Parse versions and filter for stable releases only (no pre-releases)
        stable_versions = []
        for version_str in version_strings:
            try:
                parsed_version = Version(version_str)
                if not parsed_version.is_prerelease:
                    stable_versions.append(parsed_version)
            except InvalidVersion:
                # Skip versions that can't be parsed
                continue

        if not stable_versions:
            raise Exception(f"No stable versions found for package '{package_name}'")

        # Find the latest stable version
        latest_version = max(stable_versions)

        return PackageVersionResult(
            ecosystem=Ecosystem.MavenGradle,
            package_name=package_name,
            latest_version=str(latest_version),
            digest=None,  # Not reliably available from maven-metadata.xml
            published_on=None,  # Not reliably available from maven-metadata.xml
        )

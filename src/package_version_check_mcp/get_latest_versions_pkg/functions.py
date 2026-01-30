import httpx
from docker_registry_client_async import DockerRegistryClientAsync, ImageName
from aiohttp import ClientResponseError
import urllib.parse
from yarl import URL
import re
from typing import Optional
import json
import asyncio
import tempfile
import os

from .structs import PackageVersionResult, PackageVersionRequest, PackageVersionError, Ecosystem


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
            ecosystem="pypi",
            package_name=package_name,
            latest_version=version,
            digest=digest,
            published_on=published_on,
        )


async def fetch_package_version(
    request: PackageVersionRequest,
) -> PackageVersionResult | PackageVersionError:
    """Fetch the latest version of a package from its ecosystem.

    Args:
        request: The package version request

    Returns:
        Either a PackageVersionResult on success or PackageVersionError on failure
    """
    try:
        if request.ecosystem == Ecosystem.NPM:
            return await fetch_npm_version(request.package_name)
        elif request.ecosystem == Ecosystem.Docker:
            return await fetch_docker_version(request.package_name, request.version)
        elif request.ecosystem == Ecosystem.NuGet:
            return await fetch_nuget_version(request.package_name)
        elif request.ecosystem == Ecosystem.MavenGradle:
            return await fetch_maven_gradle_version(request.package_name)
        elif request.ecosystem == Ecosystem.Helm:
            return await fetch_helm_chart_version(request.package_name, request.version)
        else:  # Ecosystem.PyPI:
            return await fetch_pypi_version(request.package_name)
    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP error {e.response.status_code}: {e.response.reason_phrase}"
        if e.response.status_code == 404:
            error_msg = f"Package '{request.package_name}' not found"
        return PackageVersionError(
            ecosystem=request.ecosystem,
            package_name=request.package_name,
            error=error_msg,
        )
    except Exception as e:
        return PackageVersionError(
            ecosystem=request.ecosystem,
            package_name=request.package_name,
            error=f"Failed to fetch package version: {str(e)}",
        )


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
            ecosystem="npm",
            package_name=package_name,
            latest_version=version,
            digest=None,  # NPM doesn't provide digest in the same way
            published_on=published_on,
        )


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
        all_versions = []
        items = package_data.get("items", [])
        for page in items:
            page_items = page.get("items", [])
            for item in page_items:
                catalog_entry = item.get("catalogEntry", {})
                version = catalog_entry.get("version")
                published = catalog_entry.get("published")

                # Filter out prerelease versions (they contain a hyphen)
                if version and "-" not in version:
                    all_versions.append({
                        "version": version,
                        "published": published
                    })

        if not all_versions:
            raise Exception(f"No stable versions found for package '{package_name}'")

        # Get the latest stable version (last in the list)
        latest = all_versions[-1]

        return PackageVersionResult(
            ecosystem="nuget",
            package_name=package_name,
            latest_version=latest["version"],
            digest=None,  # NuGet doesn't provide digest in the registration API
            published_on=latest["published"] if latest["published"] != "1900-01-01T00:00:00+00:00" else None,
        )


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
    import xml.etree.ElementTree as ET

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

        # Look for <versioning><release>...</release></versioning>
        versioning = root.find("versioning")
        if versioning is None:
            raise Exception(f"No versioning information found for package '{package_name}'")

        release = versioning.find("release")
        if release is None or not release.text:
            # Fall back to <latest> if <release> is not available
            latest = versioning.find("latest")
            if latest is None or not latest.text:
                raise Exception(f"No release or latest version found for package '{package_name}'")
            version = latest.text
        else:
            version = release.text

        return PackageVersionResult(
            ecosystem="maven_gradle",
            package_name=package_name,
            latest_version=version,
            digest=None,  # Not reliably available from maven-metadata.xml
            published_on=None,  # Not reliably available from maven-metadata.xml
        )


async def fetch_docker_version(
    package_name: str, tag_hint: Optional[str] = None
) -> PackageVersionResult:
    """Fetch the latest version tag of a Docker image.

    Args:
        package_name: Fully qualified Docker image name (e.g., 'index.docker.io/library/busybox')
        tag_hint: Optional tag hint for compatibility (e.g., '1.2-alpine'). If provided,
                  returns the latest tag matching the same suffix pattern. If omitted,
                  returns the latest semantic version tag.

    Returns:
        PackageVersionResult with the latest version tag

    Raises:
        Exception: If the image cannot be found or fetched
    """
    # Parse the image name
    image_name = ImageName.parse(package_name)

    async with DockerRegistryClientAsync() as registry_client:
        # Get all available tags
        tags = await get_docker_image_tags(image_name, registry_client)

        if not tags:
            raise Exception(f"No tags found for image '{package_name}'")

        # Determine the latest compatible version
        latest_tag = determine_latest_image_tag(tags, tag_hint)

        if not latest_tag:
            hint_msg = f" compatible with '{tag_hint}'" if tag_hint else ""
            raise Exception(f"No valid version tags{hint_msg} found for image '{package_name}'")

        # Get the manifest digest for this tag
        image_with_tag = image_name.clone()
        image_with_tag.set_tag(latest_tag)

        try:
            manifest = await registry_client.head_manifest(image_with_tag)
            # Get digest from the head_manifest response
            digest = str(manifest.digest) if manifest.digest else None
        except Exception:
            # If we can't get the manifest, proceed without digest
            digest = None

        return PackageVersionResult(
            ecosystem="docker",
            package_name=package_name,
            latest_version=latest_tag,
            digest=digest,
            published_on=None,  # Docker doesn't expose this easily via registry API
        )


async def get_docker_image_tags(image_name: ImageName, registry_client: DockerRegistryClientAsync) -> list[str]:
    # First pass, which may return all results (e.g. for Docker Hub) but maybe also only partial results
    # (if tag_list_response.client_response.links is non-empty)
    try:
        tag_list_response = await registry_client.get_tag_list(image_name)
    except ClientResponseError as e:
        if e.status == 404:
            return []
        raise

    tags: list[ImageName] = []
    tags.extend(tag_list_response.tags)

    # Second pass, retrieving additional tags when pagination is needed
    while True:
        if "next" in tag_list_response.client_response.links:
            next_link: dict[str, URL] = tag_list_response.client_response.links["next"]

            if "url" in next_link and next_link["url"].query_string:
                query = next_link["url"].query_string  # example: 'n=100&last=v0.45.0-amd64'
                result = urllib.parse.parse_qs(query)
                if "n" not in result or "last" not in result:
                    break
                tag_list_response = await registry_client.get_tag_list(image_name, **result)
                tags.extend(tag_list_response.tags)
            else:
                break
        else:
            break

    tags_as_strings: list[str] = [tag.tag for tag in tags]  # type: ignore
    return tags_as_strings


def determine_latest_image_tag(available_tags: list[str], tag_hint: Optional[str] = None) -> Optional[str]:
    """
    Get the latest compatible version from available Docker tags.

    Compatibility is determined by matching suffixes (e.g., '-alpine').

    Args:
        available_tags: List of available version tags
        tag_hint: Optional hint tag (e.g., "1.2-alpine") to determine compatibility

    Returns:
        The latest compatible version, or None if no compatible versions found

    Examples:
        >>> get_latest_version(['1.2.3', '1.2.4', '1.3.0'], '1.2')
        '1.3.0'
        >>> get_latest_version(['1.2.3-alpine', '1.3.0-alpine', '1.3.0'], '1.2-alpine')
        '1.3.0-alpine'
        >>> get_latest_version(['3.7.0', '3.8.0-alpine'], '3.7.0-alpine')
        None
    """

    def parse_tag(tag: str) -> Optional[dict]:
        """Parse a Docker tag into its components."""
        if not tag:
            return None

        # Ignore special tags like 'latest', 'stable', 'edge', etc.
        if tag.lower() in ('latest', 'stable', 'edge', 'nightly', 'dev', 'master', 'main'):
            return None

        # Ignore commit hashes (7-40 hex characters, but not purely numeric)
        if re.match(r'^[a-f0-9]{7,40}$', tag, re.IGNORECASE) and not re.match(r'^[0-9]+$', tag):
            return None

        # Remove leading 'v'
        clean_tag = re.sub(r'^v', '', tag)

        # Split on first '-' to separate version from suffix
        parts = clean_tag.split('-', 1)
        prefix = parts[0]
        suffix = parts[1] if len(parts) > 1 else ''

        # Match version pattern: numeric parts with optional prerelease
        match = re.match(r'^(?P<version>\d+(?:\.\d+)*)(?P<prerelease>\w*)$', prefix)
        if not match:
            return None

        version_str = match.group('version')
        prerelease = match.group('prerelease')

        # Ignore tags where version is only a large number (>=1000) without dots
        # This filters out date-based tags like 20260202, 20250115, etc.
        if '.' not in version_str:
            try:
                if int(version_str) >= 1000:
                    return None
            except ValueError:
                pass

        # Split version into numeric parts
        release = [int(x) for x in version_str.split('.')]

        return {
            'release': release,
            'suffix': suffix,
            'prerelease': prerelease,
            'original': tag
        }

    def is_stable(parsed: dict) -> bool:
        """Check if a version is stable (no prerelease marker)."""
        return not parsed['prerelease']

    def version_sort_key(parsed: dict) -> tuple:
        """
        Generate a sort key for version comparison.

        Returns a tuple that can be used for sorting:
        - release parts (padded to same length)
        - prerelease (empty string sorts after non-empty, for stable versions)
        - suffix (reversed for proper ordering)
        """
        # Pad release to consistent length for comparison
        release = parsed['release'] + [0] * (10 - len(parsed['release']))

        # Empty prerelease (stable) should sort after prerelease versions
        # We invert this by using tuple ordering
        prerelease_key = (not parsed['prerelease'], parsed['prerelease'])

        return (release, prerelease_key)

    # Parse all tags
    parsed_tags = []
    for tag in available_tags:
        parsed = parse_tag(tag)
        if parsed:
            parsed_tags.append(parsed)

    if not parsed_tags:
        return None

    # If no hint provided, find the latest stable version overall
    if tag_hint is None:
        # Prefer stable versions
        stable_tags = [p for p in parsed_tags if is_stable(p)]
        candidates = stable_tags if stable_tags else parsed_tags

        # Among stable versions, prefer those without suffixes
        no_suffix_candidates = [p for p in candidates if not p['suffix']]
        if no_suffix_candidates:
            candidates = no_suffix_candidates

        # Sort and return the latest
        candidates.sort(key=version_sort_key)
        return candidates[-1]['original']

    # Parse the hint to determine compatibility requirements
    hint_parsed = parse_tag(tag_hint)
    if not hint_parsed:
        return None

    # Find compatible versions (matching suffix only)
    hint_suffix = hint_parsed['suffix']
    compatible = [p for p in parsed_tags if p['suffix'] == hint_suffix]

    if not compatible:
        return None

    # If hint is stable, prefer stable compatible versions
    if is_stable(hint_parsed):
        stable_compatible = [p for p in compatible if is_stable(p)]
        if stable_compatible:
            compatible = stable_compatible

    # Sort and return the latest compatible version
    compatible.sort(key=version_sort_key)
    return compatible[-1]['original']


def parse_helm_chart_name(package_name: str) -> tuple[str, str, str]:
    """Parse a Helm chart name into its components.

    Supports two formats:
    1. ChartMuseum URL: "https://host/path/chart-name"
    2. OCI reference: "oci://host/path/chart-name"

    Args:
        package_name: The Helm chart reference

    Returns:
        A tuple of (registry_type, registry_url, chart_name)
        - registry_type: Either "chartmuseum" or "oci"
        - registry_url: The base URL for the registry (without chart name)
        - chart_name: The name of the chart

    Raises:
        ValueError: If the chart name format is invalid
    """
    if package_name.startswith("oci://"):
        # OCI format: oci://host/path/chart-name
        rest = package_name[6:]  # Remove "oci://"
        if "/" not in rest:
            raise ValueError(
                f"Invalid Helm OCI chart reference: '{package_name}'. "
                "Expected format: 'oci://host/path/chart-name'"
            )
        # Split to get registry and chart path
        last_slash = rest.rfind("/")
        registry_url = rest[:last_slash]
        chart_name = rest[last_slash + 1:]

        if not registry_url or not chart_name:
            raise ValueError(
                f"Invalid Helm OCI chart reference: '{package_name}'. "
                "Expected format: 'oci://host/path/chart-name'"
            )

        return "oci", registry_url, chart_name

    elif package_name.startswith("https://") or package_name.startswith("http://"):
        # ChartMuseum format: https://host/path/chart-name
        # We need to extract chart name from the end of the URL
        parsed = urllib.parse.urlparse(package_name)
        path = parsed.path.rstrip("/")

        if not path or "/" not in path:
            raise ValueError(
                f"Invalid Helm ChartMuseum URL: '{package_name}'. "
                "Expected format: 'https://host/path/chart-name'"
            )

        # Extract chart name from the last segment
        last_slash = path.rfind("/")
        chart_name = path[last_slash + 1:]
        base_path = path[:last_slash]

        if not chart_name:
            raise ValueError(
                f"Invalid Helm ChartMuseum URL: '{package_name}'. "
                "Expected format: 'https://host/path/chart-name'"
            )

        # Reconstruct the base registry URL
        registry_url = f"{parsed.scheme}://{parsed.netloc}{base_path}"

        return "chartmuseum", registry_url, chart_name

    else:
        raise ValueError(
            f"Invalid Helm chart reference: '{package_name}'. "
            "Expected format: 'https://host/path/chart-name' (ChartMuseum) or 'oci://host/path/chart-name' (OCI)"
        )


async def fetch_helm_chart_version(
    package_name: str, version_hint: Optional[str] = None
) -> PackageVersionResult:
    """Fetch the latest version of a Helm chart.

    Supports both ChartMuseum (https://) and OCI (oci://) registries.

    Args:
        package_name: The Helm chart reference in one of these formats:
            - ChartMuseum: "https://host/path/chart-name"
            - OCI: "oci://host/path/chart-name"
        version_hint: Optional version hint for compatibility matching

    Returns:
        PackageVersionResult with the latest version information

    Raises:
        Exception: If the chart cannot be found or fetched
    """
    registry_type, registry_url, chart_name = parse_helm_chart_name(package_name)

    if registry_type == "oci":
        return await fetch_helm_oci_version(registry_url, chart_name, package_name, version_hint)
    else:
        return await fetch_helm_chartmuseum_version(registry_url, chart_name, package_name)


async def fetch_helm_chartmuseum_version(
    registry_url: str, chart_name: str, original_package_name: str
) -> PackageVersionResult:
    """Fetch the latest version of a Helm chart from a ChartMuseum-compatible registry.

    Uses yq (fast Go-based YAML processor) to extract only the needed chart from large index.yaml files.

    Args:
        registry_url: The base URL of the ChartMuseum registry
        chart_name: The name of the chart
        original_package_name: The original package name for the result

    Returns:
        PackageVersionResult with the latest version information

    Raises:
        Exception: If the chart cannot be found or fetched
    """
    # ChartMuseum serves index.yaml at the registry root
    index_url = f"{registry_url}/index.yaml"

    # Stream the YAML file directly to disk to avoid loading potentially large files (20MB+)
    # into memory
    temp_file = None
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            async with client.stream('GET', index_url) as response:
                response.raise_for_status()

                # Create temp file and stream response to it
                temp_file = tempfile.NamedTemporaryFile(mode='wb', suffix='.yaml', delete=False)
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    temp_file.write(chunk)
                temp_file.close()

        # Use yq to extract only the specific chart (much faster than parsing entire YAML)
        chart_versions = await _extract_helm_chart_with_yq(temp_file.name, chart_name)

        if not chart_versions:
            raise Exception(f"Chart '{chart_name}' not found in repository at {registry_url}")

        # Filter out deprecated charts and find the latest semantic version
        latest_version = None
        latest_digest = None
        latest_created = None

        for version_entry in chart_versions:
            # Skip deprecated charts
            if version_entry.get("deprecated", False):
                continue

            version = version_entry.get("version")
            if not version:
                continue

            # Skip prerelease versions
            _, prerelease = _parse_semver(version)
            if prerelease:
                continue

            # Use semantic version comparison to find the latest
            if latest_version is None or _compare_semver(version, latest_version) > 0:
                latest_version = version
                latest_digest = version_entry.get("digest")
                latest_created = version_entry.get("created")

        if not latest_version:
            raise Exception(f"No non-deprecated stable versions found for chart '{chart_name}'")

        return PackageVersionResult(
            ecosystem="helm",
            package_name=original_package_name,
            latest_version=latest_version,
            digest=latest_digest,
            published_on=latest_created,
        )
    finally:
        # Clean up temp file
        if temp_file:
            try:
                os.unlink(temp_file.name)
            except Exception:
                pass


async def fetch_helm_oci_version(
    registry_url: str, chart_name: str, original_package_name: str, version_hint: Optional[str] = None
) -> PackageVersionResult:
    """Fetch the latest version of a Helm chart from an OCI registry.

    Reuses the Docker registry client to query OCI registries.

    Args:
        registry_url: The registry host and path (without oci:// prefix)
        chart_name: The name of the chart
        original_package_name: The original package name for the result
        version_hint: Optional version hint for compatibility matching

    Returns:
        PackageVersionResult with the latest version information

    Raises:
        Exception: If the chart cannot be found or fetched
    """
    # Construct the full OCI image reference
    # OCI Helm charts are stored as OCI artifacts, queryable like Docker images
    full_image_name = f"{registry_url}/{chart_name}"

    # Parse as a Docker image name
    image_name = ImageName.parse(full_image_name)

    async with DockerRegistryClientAsync() as registry_client:
        # Get all available tags (versions)
        tags = await get_docker_image_tags(image_name, registry_client)

        if not tags:
            raise Exception(f"No versions found for Helm chart '{original_package_name}'")

        # Determine the latest compatible version using the same logic as Docker
        latest_tag = determine_latest_image_tag(tags, version_hint)

        if not latest_tag:
            hint_msg = f" compatible with '{version_hint}'" if version_hint else ""
            raise Exception(f"No valid version tags{hint_msg} found for Helm chart '{original_package_name}'")

        # Get the manifest digest for this tag
        image_with_tag = image_name.clone()
        image_with_tag.set_tag(latest_tag)

        try:
            manifest = await registry_client.head_manifest(image_with_tag)
            digest = str(manifest.digest) if manifest.digest else None
        except Exception:
            digest = None

        return PackageVersionResult(
            ecosystem="helm",
            package_name=original_package_name,
            latest_version=latest_tag,
            digest=digest,
            published_on=None,  # OCI registries don't expose this easily
        )


async def _extract_helm_chart_with_yq(yaml_file_path: str, chart_name: str) -> list[dict]:
    """Extract a specific chart's versions from Helm index.yaml using yq (fast Go-based tool).

    This avoids parsing the entire YAML file (which can be 20MB+) by using yq to extract
    only the specific chart we need.

    Args:
        yaml_file_path: Path to the index.yaml file on disk
        chart_name: The name of the chart to extract

    Returns:
        List of version dictionaries for the chart
    """
    try:
        # Use yq to extract just the chart we need and output as JSON
        # yq syntax: .entries["chart-name"] -o json
        process = await asyncio.create_subprocess_exec(
            'yq',
            f'.entries["{chart_name}"]',
            '-o', 'json',
            yaml_file_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, _stderr = await process.communicate()

        if process.returncode != 0:
            # yq not found or error - return empty list
            return []

        # Parse the JSON output
        result = json.loads(stdout.decode())

        # yq returns null if the key doesn't exist
        if result is None:
            return []

        return result if isinstance(result, list) else []

    except FileNotFoundError:
        # yq not installed - return empty list to trigger fallback
        return []
    except Exception:
        return []


def _parse_semver(version: str) -> tuple[list[int], str]:
    """Parse a semantic version into numeric parts and prerelease suffix.

    Args:
        version: The version string to parse (e.g., "1.2.3", "v2.0.0-beta.1")

    Returns:
        A tuple of (numeric_parts, prerelease) where:
        - numeric_parts: List of integers from the version (e.g., [1, 2, 3])
        - prerelease: The prerelease suffix if any (e.g., "beta.1"), empty string otherwise
    """
    # Remove leading 'v' if present
    v = version.lstrip('v')

    # Split on '-' to separate version from prerelease
    parts = v.split('-', 1)
    version_str = parts[0]
    prerelease = parts[1] if len(parts) > 1 else ''

    # Parse numeric parts
    numeric_parts = []
    for part in version_str.split('.'):
        try:
            numeric_parts.append(int(part))
        except ValueError:
            # Handle non-numeric parts
            numeric_parts.append(0)

    return numeric_parts, prerelease


def _compare_semver(version1: str, version2: str) -> int:
    """Compare two semantic version strings.

    Assumes stable versions only (no prerelease comparison).

    Args:
        version1: First version string
        version2: Second version string

    Returns:
        -1 if version1 < version2
        0 if version1 == version2
        1 if version1 > version2
    """
    v1_parts, _ = _parse_semver(version1)
    v2_parts, _ = _parse_semver(version2)

    # Pad to same length
    max_len = max(len(v1_parts), len(v2_parts))
    v1_parts.extend([0] * (max_len - len(v1_parts)))
    v2_parts.extend([0] * (max_len - len(v2_parts)))

    # Compare numeric parts
    for p1, p2 in zip(v1_parts, v2_parts):
        if p1 < p2:
            return -1
        if p1 > p2:
            return 1

    return 0

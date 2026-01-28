import httpx
from docker_registry_client_async import DockerRegistryClientAsync, ImageName
from aiohttp import ClientResponseError
import urllib.parse
from yarl import URL
import re
from typing import Optional

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
        elif request.ecosystem == Ecosystem.DOCKER:
            return await fetch_docker_version(request.package_name, request.version)
        else: # Ecosystem.PYPI:
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

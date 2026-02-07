"""Docker image version fetcher."""

import urllib.parse
from typing import Optional

from aiohttp import ClientResponseError
from docker_registry_client_async import DockerRegistryClientAsync, ImageName
from yarl import URL

from ..structs import PackageVersionResult, Ecosystem
from ..utils.version_parser import parse_docker_tag


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
            ecosystem=Ecosystem.Docker,
            package_name=package_name,
            latest_version=latest_tag,
            digest=digest,
            published_on=None,  # Docker doesn't expose this easily via registry API
        )


async def get_docker_image_tags(image_name: ImageName, registry_client: DockerRegistryClientAsync) -> list[str]:
    """Get all tags for a Docker image, handling pagination.

    Args:
        image_name: The parsed Docker image name
        registry_client: The Docker registry client

    Returns:
        List of all tags for the image
    """
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
    """Get the latest compatible version from available Docker tags.

    Compatibility is determined by matching suffixes (e.g., '-alpine').

    Args:
        available_tags: List of available version tags
        tag_hint: Optional hint tag (e.g., "1.2-alpine") to determine compatibility

    Returns:
        The latest compatible version, or None if no compatible versions found

    Examples:
        >>> determine_latest_image_tag(['1.2.3', '1.2.4', '1.3.0'], '1.2')
        '1.3.0'
        >>> determine_latest_image_tag(['1.2.3-alpine', '1.3.0-alpine', '1.3.0'], '1.2-alpine')
        '1.3.0-alpine'
        >>> determine_latest_image_tag(['3.7.0', '3.8.0-alpine'], '3.7.0-alpine')
        None
    """

    def is_stable(parsed: dict) -> bool:
        """Check if a version is stable (no prerelease marker)."""
        return not parsed['prerelease']

    def version_sort_key(parsed: dict) -> tuple:
        """Generate a sort key for version comparison.

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
        parsed = parse_docker_tag(tag)
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
    hint_parsed = parse_docker_tag(tag_hint)
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

"""Helm chart version fetcher."""

import asyncio
import os
import tempfile
import textwrap
import urllib.parse
from typing import Optional, List, Dict, Any

import httpx
import yaml
from docker_registry_client_async import DockerRegistryClientAsync, ImageName

from .docker import get_docker_image_tags, determine_latest_image_tag
from ..structs import PackageVersionResult, Ecosystem
from ...utils.version_parser import Version, InvalidVersion


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


async def fetch_helm_chart_version(package_name: str, version_hint: Optional[str] = None) -> PackageVersionResult:
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

    Uses a memory-efficient streaming YAML parser to extract only the needed chart from large index.yaml files.

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
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            async with client.stream('GET', index_url) as response:
                response.raise_for_status()

                # Create temp file and stream response to it
                temp_file = tempfile.NamedTemporaryFile(mode='wb', suffix='.yaml', delete=False)
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    temp_file.write(chunk)
                temp_file.close()

        # Run the CPU-bound YAML parsing in a separate thread
        chart_versions = await asyncio.to_thread(
            _extract_helm_chart_versions_memory_efficient, temp_file.name, chart_name
        )

        if not chart_versions:
            raise Exception(f"Chart '{chart_name}' not found in repository at {registry_url}")

        # Filter out deprecated charts and find the latest semantic version
        latest_version: Optional[Version] = None
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
            try:
                v_obj = Version(version)
                if v_obj.is_prerelease:
                    continue
            except InvalidVersion:
                continue

            # Use semantic version comparison to find the latest
            if latest_version is None or v_obj > latest_version:
                latest_version = v_obj
                latest_digest = version_entry.get("digest")
                latest_created = version_entry.get("created")

        if not latest_version:
            raise Exception(f"No non-deprecated stable versions found for chart '{chart_name}'")

        return PackageVersionResult(
            ecosystem=Ecosystem.Helm,
            package_name=original_package_name,
            latest_version=str(latest_version),
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


async def fetch_helm_oci_version(registry_url: str, chart_name: str, original_package_name: str,
                                 version_hint: Optional[str] = None) -> PackageVersionResult:
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
            ecosystem=Ecosystem.Helm,
            package_name=original_package_name,
            latest_version=latest_tag,
            digest=digest,
            published_on=None,  # OCI registries don't expose this easily
        )


def _extract_helm_chart_versions_memory_efficient(yaml_path: str, chart_name: str) -> List[Dict[str, Any]]:
    """
    Parses a specific entry of a Helm index.yaml file memory-efficiently.

    Args:
        yaml_path (str): Path to the index.yaml file.
        chart_name (str): The name of the chart to extract.

    Returns:
        list: A list of dicts containing version info, or empty list if not found.
    """
    start_line = -1
    end_line = -1

    # Try using CSafeLoader for speed if available, otherwise fallback to SafeLoader
    try:
        Loader = yaml.CSafeLoader
    except AttributeError:
        Loader = yaml.SafeLoader

    # 1. First pass: Parse events to find coordinates
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            events = yaml.parse(f, Loader=Loader)

            # State machine states
            STATE_SEARCH_ENTRIES = 0  # searching for 'entries' key
            STATE_WAIT_ENTRIES_VAL = 1  # waiting for entries mapping start
            STATE_SEARCH_CHART = 2  # searching for chart name key
            STATE_WAIT_CHART_VAL = 3  # waiting for chart's versions sequence to start
            STATE_CAPTURE_VALUE = 4  # capturing a specific version's dict

            state = STATE_SEARCH_ENTRIES
            depth = 0

            entries_depth = -1
            target_seq_depth = -1

            for event in events:
                # Track depth changes for Mapping and Sequence
                if isinstance(event, (yaml.MappingStartEvent, yaml.SequenceStartEvent)):
                    depth += 1
                elif isinstance(event, (yaml.MappingEndEvent, yaml.SequenceEndEvent)):
                    depth -= 1

                    # Check if we finished capturing the target value
                    if state == STATE_CAPTURE_VALUE and depth < target_seq_depth:
                        # We have popped back up from the sequence
                        end_line = event.end_mark.line
                        break

                if state == STATE_SEARCH_ENTRIES:
                    # We expect 'entries' at the top level or close to it
                    if isinstance(event, yaml.ScalarEvent) and event.value == 'entries':
                        state = STATE_WAIT_ENTRIES_VAL

                elif state == STATE_WAIT_ENTRIES_VAL:
                    if isinstance(event, yaml.MappingStartEvent):
                        entries_depth = depth  # The depth INSIDE the entries mapping
                        state = STATE_SEARCH_CHART

                elif state == STATE_SEARCH_CHART:
                    # Strict check: Match chart name AND ensure we are at the top level of 'entries'
                    if isinstance(event, yaml.ScalarEvent) and event.value == chart_name and depth == entries_depth:
                        state = STATE_WAIT_CHART_VAL
                    elif isinstance(event, yaml.MappingEndEvent) and depth < entries_depth:
                        # We left the entries mapping without finding the chart
                        return []

                elif state == STATE_WAIT_CHART_VAL:
                    if isinstance(event, yaml.SequenceStartEvent):
                        start_line = event.start_mark.line
                        target_seq_depth = depth  # The depth INSIDE the sequence
                        state = STATE_CAPTURE_VALUE
                    else:
                        pass
    except Exception:
        # Fallback or error in parsing structure
        return []

    if start_line == -1:
        return []

    # 2. Extract lines to temporary file
    lines_to_write = []

    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            # Note: enumerate is 0-indexed, which matches start_mark.line
            for i, line in enumerate(f):
                if i >= start_line:
                    # end_line corresponds to the line number of the event end mark.
                    # For block sequences ending with dedent, this mark is often on the line
                    # containing the *next* token (e.g., the next chart key).
                    # We typically want to EXCLUDE this line.
                    if end_line != -1 and i >= end_line:
                        break
                    lines_to_write.append(line)
    except Exception:
        return []

    if not lines_to_write:
        return []

    # 3. Clean up indentation (Dedent)
    raw_content = "".join(lines_to_write)
    dedented_content = textwrap.dedent(raw_content)

    # 4. Write temp file and load
    tmp_file_extract = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
    try:
        tmp_file_extract.write(dedented_content)
        tmp_file_extract.close()

        with open(tmp_file_extract.name, 'r') as tf:
            # Use safe_load as it's standard.
            data = yaml.safe_load(tf)
            if isinstance(data, list):
                if data[0]["name"] != chart_name:
                    raise ValueError("Extracted Helm chart name does not match requested chart name")
                return data
            raise ValueError("Extracted Helm chart versions is not a list")


    except Exception:
        return []
    finally:
        if os.path.exists(tmp_file_extract.name):
            try:
                os.remove(tmp_file_extract.name)
            except Exception:
                pass

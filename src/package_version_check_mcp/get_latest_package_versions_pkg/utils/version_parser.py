"""Utilities for parsing and comparing semantic versions."""

import re
from typing import Optional


def parse_docker_tag(tag: str) -> Optional[dict]:
    """Parse a Docker tag into its components.

    Args:
        tag: The Docker tag to parse

    Returns:
        A dictionary with parsed components, or None if the tag is invalid:
        - release: List of integer version parts
        - suffix: String suffix (e.g., 'alpine', 'slim')
        - prerelease: Prerelease identifier
        - original: The original tag
    """
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

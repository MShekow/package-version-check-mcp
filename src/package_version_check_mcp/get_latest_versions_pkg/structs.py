from enum import Enum
from typing import Optional

from pydantic import BaseModel


class Ecosystem(str, Enum):
    """Supported package ecosystems."""

    NPM = "npm"
    PYPI = "pypi"


class PackageVersionRequest(BaseModel):
    """Request for a package version lookup."""

    ecosystem: Ecosystem
    package_name: str
    version: Optional[str] = None


class PackageVersionResult(BaseModel):
    """Successful package version lookup result."""

    ecosystem: str
    package_name: str
    latest_version: str
    digest: Optional[str] = None
    published_on: Optional[str] = None


class PackageVersionError(BaseModel):
    """Error during package version lookup."""

    ecosystem: str
    package_name: str
    error: str


class GetLatestVersionsResponse(BaseModel):
    """Response from get_latest_versions tool."""

    result: list[PackageVersionResult]
    lookup_errors: list[PackageVersionError]

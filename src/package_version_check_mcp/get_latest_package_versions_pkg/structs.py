from enum import Enum
from typing import Optional

from pydantic import BaseModel


class Ecosystem(str, Enum):
    """Supported package ecosystems."""

    NPM = "npm"
    PyPI = "pypi"
    Docker = "docker"
    NuGet = "nuget"
    MavenGradle = "maven_gradle"
    Helm = "helm"
    TerraformProvider = "terraform_provider"
    TerraformModule = "terraform_module"
    Go = "go"
    PHP = "php"
    RubyGems = "rubygems"
    Rust = "rust"
    Swift = "swift"
    Dart = "dart"


class PackageVersionRequest(BaseModel):
    """Request for a package version lookup."""

    ecosystem: Ecosystem
    package_name: str
    version_hint: Optional[str] = None


class PackageVersionResult(BaseModel):
    """Successful package version lookup result."""

    ecosystem: Ecosystem
    package_name: str
    latest_version: str
    digest: Optional[str] = None
    published_on: Optional[str] = None


class PackageVersionError(BaseModel):
    """Error during package version lookup."""

    ecosystem: Ecosystem
    package_name: str
    error: str


class GetLatestVersionsResponse(BaseModel):
    """Response from get_latest_package_versions tool."""

    result: list[PackageVersionResult]
    lookup_errors: list[PackageVersionError]

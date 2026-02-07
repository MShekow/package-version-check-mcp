"""Terraform provider and module version fetchers."""

from typing import Callable

import httpx

from ..structs import PackageVersionResult, Ecosystem
from ...utils.version_parser import Version, InvalidVersion


def parse_terraform_provider_name(package_name: str) -> tuple[str, str, str]:
    """Parse a Terraform provider package name into registry, namespace, and type.

    Args:
        package_name: Provider name in format "[registry/]<namespace>/<type>"
                      If registry is omitted, registry.terraform.io is assumed.
                      Examples:
                        - "hashicorp/aws" (defaults to registry.terraform.io)
                        - "registry.terraform.io/hashicorp/aws"
                        - "registry.opentofu.org/hashicorp/aws"

    Returns:
        A tuple of (registry_url, namespace, provider_type)

    Raises:
        ValueError: If the package name format is invalid
    """
    parts = package_name.split("/")

    if len(parts) == 2:
        # No registry specified, use default Terraform Registry
        registry = "registry.terraform.io"
        namespace, provider_type = parts
    elif len(parts) == 3:
        # Registry specified
        registry, namespace, provider_type = parts
    else:
        raise ValueError(
            f"Invalid Terraform provider name format: '{package_name}'. "
            "Expected format: '[registry/]<namespace>/<type>' "
            "(e.g., 'hashicorp/aws' or 'registry.terraform.io/hashicorp/aws')"
        )

    if not namespace or not provider_type:
        raise ValueError(
            f"Invalid Terraform provider name: '{package_name}'. "
            "Both namespace and type must be non-empty."
        )

    return registry, namespace, provider_type


def parse_terraform_module_name(package_name: str) -> tuple[str, str, str, str]:
    """Parse a Terraform module package name into registry, namespace, name, and provider.

    Args:
        package_name: Module name in format "[registry/]<namespace>/<name>/<provider>"
                      If registry is omitted, registry.terraform.io is assumed.
                      Examples:
                        - "terraform-aws-modules/vpc/aws" (defaults to registry.terraform.io)
                        - "registry.terraform.io/terraform-aws-modules/vpc/aws"
                        - "registry.opentofu.org/terraform-aws-modules/vpc/aws"

    Returns:
        A tuple of (registry_url, namespace, module_name, provider)

    Raises:
        ValueError: If the package name format is invalid
    """
    parts = package_name.split("/")

    if len(parts) == 3:
        # No registry specified, use default Terraform Registry
        registry = "registry.terraform.io"
        namespace, module_name, provider = parts
    elif len(parts) == 4:
        # Registry specified
        registry, namespace, module_name, provider = parts
    else:
        raise ValueError(
            f"Invalid Terraform module name format: '{package_name}'. "
            "Expected format: '[registry/]<namespace>/<name>/<provider>' "
            "(e.g., 'terraform-aws-modules/vpc/aws' or 'registry.terraform.io/terraform-aws-modules/vpc/aws')"
        )

    if not namespace or not module_name or not provider:
        raise ValueError(
            f"Invalid Terraform module name: '{package_name}'. "
            "Namespace, name, and provider must all be non-empty."
        )

    return registry, namespace, module_name, provider


async def _fetch_terraform_registry_version(url: str, package_name: str, ecosystem: Ecosystem,
                                            extract_versions: Callable[[dict], list], ) -> PackageVersionResult:
    """Shared helper for fetching module or provider versions from a Terraform registry.

    Args:
        url: The API URL to fetch versions from
        package_name: The original package name for error messages and result
        ecosystem: The ecosystem for the result (e.g., Ecosystem.TerraformProvider, Ecosystem.TerraformModule)
        extract_versions: A callable that extracts the versions list from the API response data

    Returns:
        PackageVersionResult with the latest version information

    Raises:
        Exception: If the package cannot be found or fetched
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()

        versions_list = extract_versions(data)
        if not versions_list:
            raise Exception(f"No versions found for '{package_name}'")

        # Filter out prerelease versions and find the latest stable version
        stable_versions = []
        for v in versions_list:
            version_str = v.get("version", "")
            if version_str and "-" not in version_str:
                stable_versions.append(version_str)

        if not stable_versions:
            # Fall back to all versions if no stable versions found
            stable_versions = [v.get("version", "") for v in versions_list if v.get("version")]

        if not stable_versions:
            raise Exception(f"No valid versions found for '{package_name}'")

        def _safe_version_key(v_str: str) -> Version:
            try:
                return Version(v_str)
            except InvalidVersion:
                return Version("0.0.0")

        # Sort versions and get the latest
        stable_versions.sort(key=_safe_version_key, reverse=True)
        latest_version = stable_versions[0]

        return PackageVersionResult(
            ecosystem=ecosystem,
            package_name=package_name,
            latest_version=latest_version,
            digest=None,  # Terraform registry doesn't provide a single digest at version level
            published_on=None,  # Not readily available from the versions endpoint
        )


async def fetch_terraform_provider_version(package_name: str) -> PackageVersionResult:
    """Fetch the latest version of a Terraform provider.

    Args:
        package_name: Provider name in format "[registry/]<namespace>/<type>"
                      If registry is omitted, registry.terraform.io is assumed.
                      Examples:
                        - "hashicorp/aws" (defaults to registry.terraform.io)
                        - "registry.terraform.io/hashicorp/aws"
                        - "registry.opentofu.org/hashicorp/aws"

    Returns:
        PackageVersionResult with the latest version information

    Raises:
        Exception: If the provider cannot be found or fetched
    """
    registry, namespace, provider_type = parse_terraform_provider_name(package_name)
    url = f"https://{registry}/v1/providers/{namespace}/{provider_type}/versions"

    return await _fetch_terraform_registry_version(
        url=url,
        package_name=package_name,
        ecosystem=Ecosystem.TerraformProvider,
        extract_versions=lambda data: data.get("versions", []),
    )


async def fetch_terraform_module_version(package_name: str) -> PackageVersionResult:
    """Fetch the latest version of a Terraform module.

    Args:
        package_name: Module name in format "[registry/]<namespace>/<name>/<provider>"
                      If registry is omitted, registry.terraform.io is assumed.
                      Examples:
                        - "terraform-aws-modules/vpc/aws" (defaults to registry.terraform.io)
                        - "registry.terraform.io/terraform-aws-modules/vpc/aws"
                        - "registry.opentofu.org/terraform-aws-modules/vpc/aws"

    Returns:
        PackageVersionResult with the latest version information

    Raises:
        Exception: If the module cannot be found or fetched
    """
    registry, namespace, module_name, provider = parse_terraform_module_name(package_name)
    url = f"https://{registry}/v1/modules/{namespace}/{module_name}/{provider}/versions"

    def extract_module_versions(data: dict) -> list:
        modules_list = data.get("modules", [])
        if not modules_list:
            return []
        return modules_list[0].get("versions", [])

    return await _fetch_terraform_registry_version(
        url=url,
        package_name=package_name,
        ecosystem=Ecosystem.TerraformModule,
        extract_versions=extract_module_versions,
    )

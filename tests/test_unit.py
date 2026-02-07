from dataclasses import dataclass

import pytest
from package_version_check_mcp.get_latest_package_versions_pkg.fetchers.docker import determine_latest_image_tag
from package_version_check_mcp.get_latest_package_versions_pkg.fetchers.maven import parse_maven_package_name
from package_version_check_mcp.get_latest_package_versions_pkg.fetchers.terraform import (
    parse_terraform_provider_name,
    parse_terraform_module_name,
)
from package_version_check_mcp.utils.version_parser import Version, InvalidVersion


@dataclass
class ExpectedVersion:
    """Expected values for version parsing tests."""
    release: tuple[int, ...]
    major: int | None = None
    minor: int | None = None
    micro: int | None = None
    pre: tuple[str, int] | None = None
    post: int | None = None
    dev: int | None = None
    variant: str | None = None
    is_prerelease: bool = False
    is_postrelease: bool = False
    is_devrelease: bool = False
    str: str | None = None
    public: str | None = None
    base_version: str | None = None


@pytest.mark.parametrize(
    "available_tags,tag_hint,expected_result,test_description",
    [
        # Test 1: Basic version upgrade
        (
            ['1.2.3', '1.2.4', '1.3.0', '2.0.0'],
            '1.2',
            '2.0.0',
            "Basic version upgrade - most specific, compatible version"
        ),
        # Test 2: Suffix compatibility (alpine)
        (
            ['1.2.3-alpine', '1.3.0-alpine', '1.3.0', '1.4.0-alpine'],
            '1.2-alpine',
            '1.4.0-alpine',
            "Suffix compatibility - should match -alpine suffix"
        ),
        # Test 3: No compatible versions
        (
            ['3.7.0', '3.8.0'],
            '3.7.0-alpine',
            None,
            "No compatible versions - no -alpine tags available"
        ),
        # Test 4: Prerelease handling
        (
            ['3.7.0', '3.7.0b1', '3.8.0b1', '3.8.0'],
            '3.7.0',
            '3.8.0',
            "Prerelease handling - prefer stable versions over prereleases"
        ),
        # Test 5: No hint provided
        (
            ['1.2.3', '2.0.0', '1.5.0', '1.5.0-alpine', '2.0.0-alpine'],
            None,
            '2.0.0',
            "No hint provided - return latest stable version, prefer no suffix"
        ),
        # Test 6: Commit hashes ignored
        (
            ['1.2.3', 'abc123def', '1.3.0', '0a1b2c3d4e5f6a7b8c9d0a1b2c3d4e5f6a7b8c9d'],
            '1.2',
            '1.3.0',
            "Commit hashes ignored - filter out hash-like tags"
        ),
        # Test 7: Special tags ignored (latest, stable, etc.)
        (
            ['latest', '1.2.3', 'stable', '1.3.0', 'nightly', '2.0.0', 'edge'],
            '1.2',
            '2.0.0',
            "Special tags ignored - filter out 'latest', 'stable', 'nightly', 'edge'"
        ),
        # Additional test cases for edge cases
        # Test 8: Empty tag list
        (
            [],
            '1.2',
            None,
            "Empty tag list - should return None"
        ),
        # Test 9: Tags with 'v' prefix
        (
            ['v1.2.3', 'v1.3.0', 'v2.0.0'],
            'v1.2',
            'v2.0.0',
            "Tags with 'v' prefix - should handle properly"
        ),
        # Test 10: Complex suffix matching
        (
            ['1.2.3-alpine3.18', '1.3.0-alpine3.18', '1.3.0-alpine3.19', '1.4.0-alpine3.18'],
            '1.2-alpine3.18',
            '1.4.0-alpine3.18',
            "Complex suffix matching - exact suffix match required"
        ),
        # Test 11: Prerelease with hint
        (
            ['3.7.0b1', '3.8.0b1', '3.8.0b2'],
            '3.7.0b1',
            '3.8.0b2',
            "Prerelease with prerelease hint - allow prerelease versions"
        ),
        # Test 12: No hint, only prereleases available
        (
            ['1.0.0rc1', '1.0.0rc2', '2.0.0b1'],
            None,
            '2.0.0b1',
            "No hint with only prereleases - return latest prerelease"
        ),
        # Test 13: Large number tags ignored (date-based tags like 20260202)
        (
            ['1.2.3', '20260202', '1.3.0', '20250115', '2.0.0'],
            '1.2',
            '2.0.0',
            "Large number tags ignored - filter out date-based tags like 20260202"
        ),
        # Test 14: Large number tags only
        (
            ['20260202', '20250115', '1000', '20240101'],
            None,
            None,
            "Large number tags only - should return None when all tags are large numbers"
        ),
        # Test 15: Small numbers without dots are allowed
        (
            ['1', '2', '10', '100', '999'],
            None,
            '999',
            "Small numbers without dots allowed - numbers <1000 are valid"
        ),
        # Test 16: Large numbers with dots are allowed
        (
            ['2024.1.15', '2025.1.15', '2026.2.2'],
            None,
            '2026.2.2',
            "Large numbers with dots allowed - semantic versions with large numbers are valid"
        ),
        # Test 17: Mixed large numbers with and without dots
        (
            ['1.2.3', '20260202', '2026.2.2', '1001', '2.0.0'],
            None,
            '2026.2.2',
            "Mixed large numbers - prefer valid semver over large numbers without dots"
        ),
    ],
)
def test_determine_latest_image_tag(available_tags, tag_hint, expected_result, test_description):
    """Test determine_latest_image_tag function with various inputs."""
    result = determine_latest_image_tag(available_tags, tag_hint)
    assert result == expected_result, f"Failed: {test_description}"


@pytest.mark.parametrize(
    "package_name,expected_registry,expected_group_id,expected_artifact_id,test_description",
    [
        # Test 1: Simple Maven Central package (no registry prefix)
        (
            "org.springframework:spring-core",
            "https://repo1.maven.org/maven2",
            "org.springframework",
            "spring-core",
            "Maven Central package - groupId:artifactId format"
        ),
        # Test 2: Package with custom registry
        (
            "https://maven.google.com:com.google.android:android",
            "https://maven.google.com",
            "com.google.android",
            "android",
            "Custom registry - full URL with https"
        ),
        # Test 3: Package with registry without https prefix
        (
            "repo.spring.io/release:org.springframework:spring-core",
            "https://repo.spring.io/release",
            "org.springframework",
            "spring-core",
            "Registry without https prefix - should add https"
        ),
        # Test 4: Package with http registry
        (
            "http://internal.repo:com.company:artifact",
            "http://internal.repo",
            "com.company",
            "artifact",
            "HTTP registry - should preserve http protocol"
        ),
        # Test 5: Registry with trailing slash
        (
            "https://maven.example.com/:org.example:mylib",
            "https://maven.example.com",
            "org.example",
            "mylib",
            "Registry with trailing slash - should remove trailing slash"
        ),
    ],
)
def test_parse_maven_package_name_success(package_name, expected_registry, expected_group_id, expected_artifact_id, test_description):
    """Test parse_maven_package_name with valid inputs."""
    registry, group_id, artifact_id = parse_maven_package_name(package_name)
    assert registry == expected_registry, f"Failed registry: {test_description}"
    assert group_id == expected_group_id, f"Failed group_id: {test_description}"
    assert artifact_id == expected_artifact_id, f"Failed artifact_id: {test_description}"


@pytest.mark.parametrize(
    "package_name,test_description",
    [
        # Test 1: Missing artifact ID
        (
            "org.springframework",
            "Missing artifact ID - only one part"
        ),
        # Test 2: Too many colons
        (
            "a:b:c:d",
            "Too many colons - four parts"
        ),
        # Test 3: Empty group ID
        (
            ":spring-core",
            "Empty group ID"
        ),
        # Test 4: Empty artifact ID
        (
            "org.springframework:",
            "Empty artifact ID"
        ),
        # Test 5: Empty package name
        (
            "",
            "Empty package name"
        ),
    ],
)
def test_parse_maven_package_name_invalid(package_name, test_description):
    """Test parse_maven_package_name with invalid inputs."""
    with pytest.raises(ValueError):
        parse_maven_package_name(package_name)


@pytest.mark.parametrize(
    "package_name,expected_registry,expected_namespace,expected_type,test_description",
    [
        # Test 1: Simple provider (namespace/type only, defaults to registry.terraform.io)
        (
            "hashicorp/aws",
            "registry.terraform.io",
            "hashicorp",
            "aws",
            "Simple provider - defaults to registry.terraform.io"
        ),
        # Test 2: Fully qualified with Terraform registry
        (
            "registry.terraform.io/hashicorp/google",
            "registry.terraform.io",
            "hashicorp",
            "google",
            "Fully qualified Terraform registry"
        ),
        # Test 3: OpenTofu registry
        (
            "registry.opentofu.org/hashicorp/random",
            "registry.opentofu.org",
            "hashicorp",
            "random",
            "OpenTofu registry - alternative registry"
        ),
        # Test 4: Third-party namespace
        (
            "integrations/github",
            "registry.terraform.io",
            "integrations",
            "github",
            "Third-party namespace provider"
        ),
        # Test 5: Custom private registry
        (
            "terraform.example.com/myorg/mycloud",
            "terraform.example.com",
            "myorg",
            "mycloud",
            "Custom private registry"
        ),
    ],
)
def test_parse_terraform_provider_name_success(package_name, expected_registry, expected_namespace, expected_type, test_description):
    """Test parse_terraform_provider_name with valid inputs."""
    registry, namespace, provider_type = parse_terraform_provider_name(package_name)
    assert registry == expected_registry, f"Failed registry: {test_description}"
    assert namespace == expected_namespace, f"Failed namespace: {test_description}"
    assert provider_type == expected_type, f"Failed provider_type: {test_description}"


@pytest.mark.parametrize(
    "package_name,test_description",
    [
        # Test 1: Missing type
        (
            "hashicorp",
            "Missing type - only one part"
        ),
        # Test 2: Too many slashes
        (
            "a/b/c/d",
            "Too many slashes - four parts"
        ),
        # Test 3: Empty namespace
        (
            "/aws",
            "Empty namespace"
        ),
        # Test 4: Empty type
        (
            "hashicorp/",
            "Empty type"
        ),
        # Test 5: Empty package name
        (
            "",
            "Empty package name"
        ),
        # Test 6: Fully qualified with empty parts
        (
            "registry.terraform.io//aws",
            "Fully qualified with empty namespace"
        ),
    ],
)
def test_parse_terraform_provider_name_invalid(package_name, test_description):
    """Test parse_terraform_provider_name with invalid inputs."""
    with pytest.raises(ValueError):
        parse_terraform_provider_name(package_name)


@pytest.mark.parametrize(
    "package_name,expected_registry,expected_namespace,expected_name,expected_provider,test_description",
    [
        # Test 1: Simple module name (no registry)
        (
            "terraform-aws-modules/vpc/aws",
            "registry.terraform.io",
            "terraform-aws-modules",
            "vpc",
            "aws",
            "Simple module name - defaults to registry.terraform.io"
        ),
        # Test 2: Fully qualified with registry
        (
            "registry.terraform.io/terraform-aws-modules/vpc/aws",
            "registry.terraform.io",
            "terraform-aws-modules",
            "vpc",
            "aws",
            "Fully qualified - explicit Terraform Registry"
        ),
        # Test 3: OpenTofu registry
        (
            "registry.opentofu.org/terraform-aws-modules/vpc/aws",
            "registry.opentofu.org",
            "terraform-aws-modules",
            "vpc",
            "aws",
            "OpenTofu registry - alternative registry"
        ),
        # Test 4: Azure module
        (
            "Azure/network/azurerm",
            "registry.terraform.io",
            "Azure",
            "network",
            "azurerm",
            "Azure module - different namespace and provider"
        ),
        # Test 5: Custom private registry
        (
            "terraform.example.com/myorg/mymodule/mycloud",
            "terraform.example.com",
            "myorg",
            "mymodule",
            "mycloud",
            "Custom private registry"
        ),
        # Test 6: Google Cloud module
        (
            "GoogleCloudPlatform/lb-http/google",
            "registry.terraform.io",
            "GoogleCloudPlatform",
            "lb-http",
            "google",
            "Google Cloud Platform module"
        ),
    ],
)
def test_parse_terraform_module_name_success(package_name, expected_registry, expected_namespace, expected_name, expected_provider, test_description):
    """Test parse_terraform_module_name with valid inputs."""
    registry, namespace, module_name, provider = parse_terraform_module_name(package_name)
    assert registry == expected_registry, f"Failed registry: {test_description}"
    assert namespace == expected_namespace, f"Failed namespace: {test_description}"
    assert module_name == expected_name, f"Failed module_name: {test_description}"
    assert provider == expected_provider, f"Failed provider: {test_description}"


@pytest.mark.parametrize(
    "package_name,test_description",
    [
        # Test 1: Missing provider (only two parts)
        (
            "terraform-aws-modules/vpc",
            "Missing provider - only two parts"
        ),
        # Test 2: Too many slashes
        (
            "a/b/c/d/e",
            "Too many slashes - five parts"
        ),
        # Test 3: Empty namespace
        (
            "/vpc/aws",
            "Empty namespace"
        ),
        # Test 4: Empty name
        (
            "terraform-aws-modules//aws",
            "Empty module name"
        ),
        # Test 5: Empty provider
        (
            "terraform-aws-modules/vpc/",
            "Empty provider"
        ),
        # Test 6: Empty package name
        (
            "",
            "Empty package name"
        ),
        # Test 7: Only one part
        (
            "terraform-aws-modules",
            "Only one part - missing name and provider"
        ),
        # Test 8: Fully qualified with empty parts
        (
            "registry.terraform.io/terraform-aws-modules//aws",
            "Fully qualified with empty module name"
        ),
    ],
)
def test_parse_terraform_module_name_invalid(package_name, test_description):
    """Test parse_terraform_module_name with invalid inputs."""
    with pytest.raises(ValueError):
        parse_terraform_module_name(package_name)


@pytest.mark.parametrize(
    "version_str,expected",
    [
        # Basic versions
        ("1.0", ExpectedVersion(release=(1, 0), major=1, minor=0, micro=0, str="1.0")),
        ("1.2.3", ExpectedVersion(release=(1, 2, 3), major=1, minor=2, micro=3, str="1.2.3")),
        ("2.0.0", ExpectedVersion(release=(2, 0, 0), major=2, minor=0, micro=0, str="2.0.0")),
        ("10.20.30", ExpectedVersion(release=(10, 20, 30), major=10, minor=20, micro=30, str="10.20.30")),
        ("0.1", ExpectedVersion(release=(0, 1), major=0, minor=1, micro=0, str="0.1")),
        ("5", ExpectedVersion(release=(5,), major=5, minor=0, micro=0, str="5")),
        ("10.20.30.40", ExpectedVersion(release=(10, 20, 30, 40), major=10, minor=20, micro=30, str="10.20.30.40")),

        # Versions with 'v' prefix (stripped in str representation)
        ("v1.0", ExpectedVersion(release=(1, 0), major=1, minor=0, micro=0, str="1.0")),
        ("v1.2.3", ExpectedVersion(release=(1, 2, 3), major=1, minor=2, micro=3, str="1.2.3")),
        ("v2.0.0", ExpectedVersion(release=(2, 0, 0), major=2, minor=0, micro=0, str="2.0.0")),

        # Prerelease versions
        ("1.0a1", ExpectedVersion(release=(1, 0), pre=('a', 1), is_prerelease=True, str="1.0a1")),
        ("1.0.alpha2", ExpectedVersion(release=(1, 0), pre=('a', 2), is_prerelease=True, str="1.0a2")),
        ("1.0b3", ExpectedVersion(release=(1, 0), pre=('b', 3), is_prerelease=True, str="1.0b3")),
        ("1.0.beta4", ExpectedVersion(release=(1, 0), pre=('b', 4), is_prerelease=True, str="1.0b4")),
        ("1.0rc5", ExpectedVersion(release=(1, 0), pre=('rc', 5), is_prerelease=True, str="1.0rc5")),
        ("1.0.rc6", ExpectedVersion(release=(1, 0), pre=('rc', 6), is_prerelease=True, str="1.0rc6")),
        ("1.0c7", ExpectedVersion(release=(1, 0), pre=('rc', 7), is_prerelease=True, str="1.0rc7")),
        ("1.0pre8", ExpectedVersion(release=(1, 0), pre=('rc', 8), is_prerelease=True, str="1.0rc8")),
        ("1.0preview9", ExpectedVersion(release=(1, 0), pre=('rc', 9), is_prerelease=True, str="1.0rc9")),
        ("1.0m1", ExpectedVersion(release=(1, 0), pre=('m', 1), is_prerelease=True, str="1.0m1")),
        ("1.0.milestone2", ExpectedVersion(release=(1, 0), pre=('m', 2), is_prerelease=True, str="1.0m2")),
        ("1.2.0-M2", ExpectedVersion(release=(1, 2, 0), pre=('m', 2), is_prerelease=True, str="1.2.0m2")),
        ("1.0.0-beta", ExpectedVersion(release=(1, 0, 0), pre=('b', 0), is_prerelease=True)),
        ("2.0.0rc1", ExpectedVersion(release=(2, 0, 0), pre=('rc', 1), is_prerelease=True)),
        ("3.1.0a1", ExpectedVersion(release=(3, 1, 0), pre=('a', 1), is_prerelease=True)),
        ("1.2.3b2", ExpectedVersion(release=(1, 2, 3), pre=('b', 2), is_prerelease=True)),
        ("8.5.2RC1", ExpectedVersion(release=(8, 5, 2), pre=('rc', 1), is_prerelease=True)),
        ("4.1.0-M1", ExpectedVersion(release=(4, 1, 0), pre=('m', 1), is_prerelease=True)),

        # Post-release versions
        ("1.0.post1", ExpectedVersion(release=(1, 0), post=1, is_postrelease=True, str="1.0.post1")),
        ("1.0-1", ExpectedVersion(release=(1, 0), post=1, is_postrelease=True, str="1.0.post1")),
        ("1.0.rev2", ExpectedVersion(release=(1, 0), post=2, is_postrelease=True, str="1.0.post2")),
        ("1.0.r3", ExpectedVersion(release=(1, 0), post=3, is_postrelease=True, str="1.0.post3")),

        # Dev-release versions
        ("1.0.dev1", ExpectedVersion(release=(1, 0), dev=1, is_devrelease=True, is_prerelease=True, str="1.0.dev1")),
        ("1.0.dev4", ExpectedVersion(release=(1, 0), dev=4, is_devrelease=True, is_prerelease=True, str="1.0.dev4")),

        # Variant versions
        ("1.0-android", ExpectedVersion(release=(1, 0), variant="android", str="1.0-android")),
        ("1.0-alpine", ExpectedVersion(release=(1, 0), variant="alpine", str="1.0-alpine")),
        ("1.0-slim", ExpectedVersion(release=(1, 0), variant="slim", str="1.0-slim")),
        ("1.2.3-11.22", ExpectedVersion(release=(1, 2, 3), variant="11.22", str="1.2.3-11.22")),
        ("1.0-foo-bar", ExpectedVersion(release=(1, 0), variant="foo-bar", str="1.0-foo-bar")),

        # Complex combinations
        ("1.0a1.post2.dev3-special", ExpectedVersion(
            release=(1, 0),
            pre=('a', 1),
            post=2,
            dev=3,
            variant="special",
            is_prerelease=True,
            is_postrelease=True,
            is_devrelease=True,
            str="1.0a1.post2.dev3-special"
        )),

        # Properties test cases
        ("1.2.3", ExpectedVersion(release=(1, 2, 3), public="1.2.3", base_version="1.2.3")),
        ("1.2.3-android", ExpectedVersion(release=(1, 2, 3), variant="android", public="1.2.3-android", base_version="1.2.3")),
    ],
)
def test_version_parsing(version_str: str, expected: ExpectedVersion):
    """Test comprehensive Version parsing covering all attributes and properties."""
    v = Version(version_str)

    # Always check release tuple
    assert v.release == expected.release

    # Check major/minor/micro if specified
    if expected.major is not None:
        assert v.major == expected.major
    if expected.minor is not None:
        assert v.minor == expected.minor
    if expected.micro is not None:
        assert v.micro == expected.micro

    # Check pre/post/dev/variant (default to None if not specified)
    assert v.pre == expected.pre
    assert v.post == expected.post
    assert v.dev == expected.dev
    assert v.variant == expected.variant

    # Check boolean properties (default to False if not specified)
    assert v.is_prerelease == expected.is_prerelease
    assert v.is_postrelease == expected.is_postrelease
    assert v.is_devrelease == expected.is_devrelease

    # Check string representation if specified
    if expected.str is not None:
        assert str(v) == expected.str

    # Check public/base_version properties if specified
    if expected.public is not None:
        assert v.public == expected.public
    if expected.base_version is not None:
        assert v.base_version == expected.base_version


@pytest.mark.parametrize("invalid_version", [
    "4.0b3_RC2",     # Invalid: underscore
    "invalid",       # Completely invalid
    "zulu-1.2.3",    # Invalid: prefix before numbers
    "",              # Empty string
    "1.0+local",     # Local version not supported
    "1!1.0",         # Epoch not supported
    "1.0-",          # Variant must have content
    "1.0-.",         # Variant must start with alphanumeric
])
def test_version_invalid(invalid_version):
    """Test that invalid version strings raise InvalidVersion."""
    with pytest.raises(InvalidVersion):
        Version(invalid_version)


@pytest.mark.parametrize(
    "version1,version2,expected_result,test_description",
    [
        # Equal versions
        ("1.2.3", "1.2.3", 0, "Equal versions"),
        ("v1.2.3", "1.2.3", 0, "Equal versions with v prefix on first"),
        ("2.0.0", "v2.0.0", 0, "Equal versions with v prefix on second"),
        ("2.0.0", "v2.0", 0, "Equal versions with v prefix on second"),

        # Less than
        ("1.2.3", "1.2.4", -1, "Patch version less"),
        ("1.2.3", "1.3.0", -1, "Minor version less"),
        ("1.2.3", "2.0.0", -1, "Major version less"),
        ("1.0", "1.0.1", -1, "Two-part vs three-part (less)"),
        ("0.9.9", "1.0.0", -1, "Pre-1.0 version less"),

        # Greater than
        ("1.2.4", "1.2.3", 1, "Patch version greater"),
        ("1.3.0", "1.2.3", 1, "Minor version greater"),
        ("2.0.0", "1.2.3", 1, "Major version greater"),
        ("1.0.1", "1.0", 1, "Three-part vs two-part (greater)"),
        ("10.0.0", "9.9.9", 1, "Double-digit major version"),

        # Prerelease handling
        ("1.0.0rc1", "1.0.0", -1, "Prerelease less than stable"),
        ("1.0.0", "1.0.0rc1", 1, "Stable greater than prerelease"),
        ("2.0.0-beta", "2.0.0", -1, "Beta less than stable"),
        ("1.0.0a1", "1.0.0b1", -1, "Alpha less than beta"),

        # Different number of parts
        ("1.2", "1.2.0", 0, "Two-part equals three-part with zero"),
        ("1", "1.0.0", 0, "One-part equals three-part with zeros"),

        # Extended comparisons from parser suite
        # Milestone
        ("1.0a1", "1.0m1", -1, "Alpha less than milestone"),
        ("1.0b1", "1.0m1", -1, "Beta less than milestone"),
        ("1.0m1", "1.0rc1", -1, "Milestone less than RC"),

        # Dev/Post/Pre ordering
        ("1.0.dev1", "1.0a1", -1, "Dev less than alpha"),
        ("1.0a1", "1.0b1", -1, "Alpha less than beta"),
        ("1.0b1", "1.0rc1", -1, "Beta less than RC"),
        ("0.9", "1.0a1", -1, "Previous major less than next alpha"),

        # Variant ordering
        ("1.0-android", "1.0", -1, "Variant less than final"),
        ("1.0-alpine", "1.0-android", -1, "Variant alpine < android (lexical)"),
        ("1.0-android", "1.0a1", 1, "Variant greater than prerelease"),
        ("1.0-android", "1.0rc1", 1, "Variant greater than RC"),
        ("1.0.post1", "1.0-android", 1, "Postrelease greater than variant"),
    ],
)
def test_version_comparison(version1, version2, expected_result, test_description):
    """Test comparison operators of Version class with various comparisons."""
    v1 = Version(version1)
    v2 = Version(version2)

    if expected_result == 0:
        assert v1 == v2, f"Failed: {test_description} (expected equality)"
    elif expected_result == -1:
        assert v1 < v2, f"Failed: {test_description} (expected v1 < v2)"
    elif expected_result == 1:
        assert v1 > v2, f"Failed: {test_description} (expected v1 > v2)"

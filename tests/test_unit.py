import pytest
from package_version_check_mcp.get_latest_versions_pkg.functions import determine_latest_image_tag, parse_maven_package_name, parse_terraform_provider_name


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

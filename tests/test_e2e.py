"""End-to-end tests for the package version check MCP server running in Docker."""

import logging
import subprocess
import time
from pathlib import Path
from typing import AsyncGenerator, Generator

import httpx
import pytest
from fastmcp import Client
from testcontainers.core.container import DockerContainer

from package_version_check_mcp.get_latest_versions_pkg.structs import Ecosystem, PackageVersionRequest, \
    GetLatestVersionsResponse

logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def docker_container_base_url() -> Generator[str, None, None]:
    """Build and run the Docker container, then clean up after tests.

    Yields:
        base_url for the running container
    """
    port = 8000
    project_root = Path(__file__).parent.parent
    image_tag = "package-version-check-mcp:test"

    logger.info("Building Docker image from: %s", project_root)

    # Build the Docker image using subprocess
    build_cmd = ["docker", "build", "-t", image_tag, str(project_root)]
    subprocess.run(
        build_cmd,
        capture_output=True,
        text=True,
        check=True
    )
    logger.info("Docker image built successfully: %s", image_tag)

    with DockerContainer(image_tag).with_exposed_ports(port) as container:
        logger.info("Docker container started: %s", container.get_container_host_ip())

        # Wait for the container to be healthy
        max_retries = 30
        retry_delay = 1
        host_port = container.get_exposed_port(port)
        base_url = f"http://{container.get_container_host_ip()}:{host_port}"

        for i in range(max_retries):
            try:
                response = httpx.get(f"{base_url}/health", timeout=2.0)
                if response.status_code == 200:
                    logger.info("Container is healthy and responding at %s", base_url)
                    break
            except (httpx.RequestError, httpx.TimeoutException) as e:
                logger.debug("Waiting for container to be ready (attempt %d/%d): %s", i+1, max_retries, e)

            if i < max_retries - 1:
                time.sleep(retry_delay)
        else:
            # Container did not become healthy - print logs for debugging
            stdout_logs = container.get_logs()[0].decode('utf-8')
            stderr_logs = container.get_logs()[1].decode('utf-8')

            logger.error("Container failed to become healthy. Stdout logs:\n%s", stdout_logs)
            logger.error("Container stderr logs:\n%s", stderr_logs)

            pytest.fail(
                f"Container did not become healthy in time.\n\n"
                f"=== STDOUT ===\n{stdout_logs}\n\n"
                f"=== STDERR ===\n{stderr_logs}"
            )

        yield base_url

        logger.info("Docker cleanup completed")


@pytest.fixture
async def mcp_client(docker_container_base_url: str) -> AsyncGenerator[Client, None]:
    """Create a FastMCP client connected to the Docker container."""
    mcp_url = f"{docker_container_base_url}/mcp"

    async with Client(mcp_url) as client:
        yield client


async def test_get_latest_package_versions_npm_success_e2e(mcp_client: Client):
    """
    Fetch a valid NPM package version from the MCP server running in Docker.

    This verifies that there are no PYTHONPATH or dependency issues within the Docker image.
    """
    result = await mcp_client.call_tool(
        name="get_latest_package_versions",
        arguments={
            "packages": [
                PackageVersionRequest(ecosystem=Ecosystem.NPM, package_name="express")
            ]
        }
    )

    assert result.structured_content is not None
    response = GetLatestVersionsResponse.model_validate(result.structured_content)
    assert len(response.result) == 1
    assert response.result[0].ecosystem == "npm"
    assert response.result[0].package_name == "express"
    assert response.result[0].latest_version != ""
    # Express should have a version like "4.x.x" or "5.x.x"
    assert "." in response.result[0].latest_version
    # Should have a publication date
    assert response.result[0].published_on is not None
    assert len(response.lookup_errors) == 0


async def test_get_latest_helm_chart_version_e2e(mcp_client: Client):
    """
    Fetch a valid Helm chart version from the MCP server running in Docker.

    This verifies that the yq binary is properly installed and accessible within
    the Docker image for parsing large Helm index.yaml files.
    """
    result = await mcp_client.call_tool(
        name="get_latest_package_versions",
        arguments={
            "packages": [
                PackageVersionRequest(ecosystem=Ecosystem.Helm, package_name="https://charts.bitnami.com/bitnami/nginx")
            ]
        }
    )

    assert result.structured_content is not None
    response = GetLatestVersionsResponse.model_validate(result.structured_content)
    assert len(response.result) == 1
    assert response.result[0].ecosystem == "helm"
    assert response.result[0].package_name == "https://charts.bitnami.com/bitnami/nginx"
    assert response.result[0].latest_version != ""
    # Helm charts should have semantic versions like "1.2.3"
    assert "." in response.result[0].latest_version
    assert len(response.lookup_errors) == 0


async def test_get_supported_tools_e2e(mcp_client: Client):
    """
    Fetch the list of supported mise tools from the MCP server running in Docker.

    This ensures that the "mise" tool is properly accessible within the Docker image.
    """
    result = await mcp_client.call_tool(
        name="get_supported_tools",
        arguments={}
    )

    assert result.structured_content is not None
    tools = result.structured_content.get("result", result.structured_content)
    assert isinstance(tools, list)
    assert len(tools) > 800
    # All entries should be strings
    assert all(isinstance(tool, str) for tool in tools)
    # Check for some well-known tools that should be in the registry
    assert "node" in tools
    assert "python" in tools


async def test_get_latest_tool_versions_php_e2e(mcp_client: Client):
    """
    Fetch the latest PHP version from the MCP server running in Docker.

    This verifies that the "mise" tool is properly installed and accessible,
    and that version filtering works correctly (excluding vendor-specific versions).
    """
    result = await mcp_client.call_tool(
        name="get_latest_tool_versions",
        arguments={
            "tool_names": ["php"]
        }
    )

    assert result.structured_content is not None
    from package_version_check_mcp.get_latest_tools_pkg.structs import GetLatestToolVersionsResponse
    response = GetLatestToolVersionsResponse.model_validate(result.structured_content)
    assert len(response.result) == 1
    assert response.result[0].tool_name == "php"
    assert response.result[0].latest_version != ""
    # PHP should have a version like "8.x.x"
    assert "." in response.result[0].latest_version
    # Ensure it's a numeric version (not vendor-specific like "zulu-8.72.0.17")
    assert response.result[0].latest_version[0].isdigit()
    assert len(response.lookup_errors) == 0


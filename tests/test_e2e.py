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
    result = subprocess.run(
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
            logs = container.get_logs()[0].decode('utf-8')
            pytest.fail(f"Container did not become healthy in time. Logs:\n{logs}")

        yield base_url

        logger.info("Docker cleanup completed")


@pytest.fixture
async def mcp_client(docker_container_base_url: str) -> AsyncGenerator[Client, None]:
    """Create a FastMCP client connected to the Docker container."""
    mcp_url = f"{docker_container_base_url}/mcp"

    async with Client(mcp_url) as client:
        yield client


async def test_get_latest_versions_npm_success_e2e(mcp_client: Client):
    """E2E test: Fetch a valid NPM package version from the MCP server running in Docker."""
    result = await mcp_client.call_tool(
        name="get_latest_versions",
        arguments={
            "packages": [
                {"ecosystem": "npm", "package_name": "express"}
            ]
        }
    )

    assert result.data is not None
    assert len(result.data.result) == 1
    assert result.data.result[0].ecosystem == "npm"
    assert result.data.result[0].package_name == "express"
    assert result.data.result[0].latest_version != ""
    # Express should have a version like "4.x.x" or "5.x.x"
    assert "." in result.data.result[0].latest_version
    # Should have a publication date
    assert result.data.result[0].published_on is not None
    assert len(result.data.lookup_errors) == 0

    logger.info("✓ E2E test passed: Got express version %s", result.data.result[0].latest_version)

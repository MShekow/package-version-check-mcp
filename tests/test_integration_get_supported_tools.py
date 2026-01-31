"""Tests for the get_supported_tools MCP tool."""

import pytest
from fastmcp import Client

from package_version_check_mcp.main import mcp


@pytest.fixture
async def mcp_client():
    """Create a FastMCP client for testing."""
    async with Client(mcp) as client:
        yield client


async def test_get_supported_tools(mcp_client: Client):
    """Test getting the list of supported tools."""
    result = await mcp_client.call_tool(
        name="get_supported_tools",
        arguments={}
    )

    assert result.structured_content is not None
    # The MCP framework wraps the response in a dict
    if isinstance(result.structured_content, dict):
        supported_tools = result.structured_content.get("result", result.structured_content)
    else:
        supported_tools = result.structured_content

    assert isinstance(supported_tools, list)
    assert len(supported_tools) > 0

    # Check that some common tools are in the list
    assert "terraform" in supported_tools
    assert "node" in supported_tools
    assert "python" in supported_tools

"""Data structures for tool version lookups."""

from pydantic import BaseModel


class LatestToolResult(BaseModel):
    """Successful tool version lookup result."""

    tool_name: str
    latest_version: str


class LatestToolError(BaseModel):
    """Error during tool version lookup."""

    tool_name: str
    error: str


class GetLatestToolVersionsResponse(BaseModel):
    """Response from get_latest_tool_versions tool."""

    result: list[LatestToolResult]
    lookup_errors: list[LatestToolError]

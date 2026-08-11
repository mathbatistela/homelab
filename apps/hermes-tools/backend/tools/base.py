"""Base class for hermes-tools plugins, shared by the REST API and the MCP server."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from pydantic import BaseModel


class EmptyParams(BaseModel):
    """Params model for tools that take no arguments."""


@dataclass
class ToolResult:
    success: bool
    data: dict = field(default_factory=dict)
    error: str = ""


class BaseTool(ABC):
    """A tool plugin registered in TOOL_SETS (tools/__init__.py).

    `params_model` describes the accepted parameters as a pydantic model — it
    drives both request validation and the input schema advertised to MCP
    clients, so REST and MCP callers see the exact same contract.
    """

    name: str = ""
    label: str = ""
    description: str = ""
    params_model: type[BaseModel] = EmptyParams

    @abstractmethod
    async def process(self, params: dict) -> ToolResult:
        """Process a request. params come from the frontend, REST caller, or MCP client."""
        ...

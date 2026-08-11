"""MCP server exposing every tool in the registry via streamable-HTTP.

Mounted at /mcp on the main FastAPI app (see main.py) and protected by an API
key checked in ApiKeyASGIMiddleware before any request reaches FastMCP —
separate from the Telegram initData auth used by the REST endpoints. Each
BaseTool's params_model becomes the MCP tool's input schema, so REST and MCP
callers share one contract; adding a tool to the registry (tools/__init__.py)
is enough to expose it here too, no per-tool MCP code needed.
"""
import logging

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from auth import check_mcp_api_key
from config import get_settings
from tools import BaseTool, ToolResult, TOOLS

logger = logging.getLogger("mcp_server")


def _make_tool_wrapper(tool: BaseTool):
    async def _wrapper(params: tool.params_model) -> dict:
        result = await tool.process(params.model_dump())
        if not result.success:
            raise RuntimeError(result.error or "Falha ao processar")
        return result.data

    _wrapper.__name__ = tool.name.replace("-", "_")
    return _wrapper


class ApiKeyASGIMiddleware:
    """Rejects any /mcp request without a valid API key before it reaches FastMCP."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        provided = headers.get(b"x-api-key", b"").decode()
        if not provided:
            auth_header = headers.get(b"authorization", b"").decode()
            if auth_header.lower().startswith("bearer "):
                provided = auth_header[7:]

        if not check_mcp_api_key(provided):
            response = JSONResponse({"detail": "API key inválida"}, status_code=401)
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)


_settings = get_settings()

mcp = FastMCP(
    "hermes-tools",
    instructions="Ferramentas de IA do hermes-tools (remoção de fundo, e mais no futuro).",
    stateless_http=True,
    streamable_http_path="/",
    transport_security=TransportSecuritySettings(
        allowed_hosts=_settings.mcp_allowed_hosts_list,
        allowed_origins=["*"],
    ),
)

for _tool in TOOLS.values():
    mcp.add_tool(_make_tool_wrapper(_tool), name=_tool.name, description=_tool.description)

# streamable_http_app() must be built once at import time: FastMCP creates its
# session manager lazily on first call, and main.py's lifespan needs
# `mcp.session_manager` to exist before the app starts serving requests.
mcp_asgi_app: ASGIApp = ApiKeyASGIMiddleware(mcp.streamable_http_app())

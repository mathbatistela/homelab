from .base import BaseTool, ToolResult
from .design.remove_bg_rmbg import RemoveBgRmbgTool

TOOLS: dict[str, BaseTool] = {
    "remove-bg": RemoveBgRmbgTool(),
}

_SETS: dict[str, dict] = {
    "design": {"name": "design", "label": "Design", "tools": ["remove-bg"]},
}


def get_tool(name: str) -> BaseTool | None:
    return TOOLS.get(name)


def list_tools(set_name: str = "") -> list[dict]:
    tools = TOOLS.values()
    if set_name and set_name in _SETS:
        tools = [TOOLS[n] for n in _SETS[set_name]["tools"] if n in TOOLS]
    return [{"name": t.name, "label": t.label, "description": t.description} for t in tools]


def list_sets() -> list[dict]:
    return list(_SETS.values())

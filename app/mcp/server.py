from typing import Any, Optional
from app.mcp.tools.base import Tool
from app.mcp.resources.base import Resource


class MCPServer:
    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._resources: dict[str, Resource] = {}

    def register_tool(self, tool: Tool):
        self._tools[tool.spec.name] = tool

    def register_resource(self, resource: Resource):
        self._resources[resource.spec.uri] = resource

    def get_tool(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def get_resource(self, uri: str) -> Optional[Resource]:
        return self._resources.get(uri)

    def list_tools(self) -> list[dict]:
        return [{"name": t.spec.name, "description": t.spec.description, "input_schema": t.spec.input_schema} for t in self._tools.values()]

    def list_resources(self) -> list[dict]:
        return [{"uri": r.spec.uri, "name": r.spec.name, "description": r.spec.description} for r in self._resources.values()]

    async def execute_tool(self, name: str, **kwargs) -> Any:
        tool = self.get_tool(name)
        if not tool:
            raise ValueError(f"Tool '{name}' not found")
        return await tool.execute(**kwargs)

    async def read_resource(self, uri: str, params: Optional[dict] = None) -> Any:
        resource = self.get_resource(uri)
        if not resource:
            raise ValueError(f"Resource '{uri}' not found")
        return await resource.read(params)

    async def write_resource(self, uri: str, data: Any, params: Optional[dict] = None) -> bool:
        resource = self.get_resource(uri)
        if not resource:
            raise ValueError(f"Resource '{uri}' not found")
        return await resource.write(data, params)

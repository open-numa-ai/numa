"""Deterministic asynchronous arithmetic Tool."""

from typing import Any

from numa.tools.arithmetic import AddInput, AddOutput
from numa.tools.async_base import AsyncTool


class AsyncAddTool(AsyncTool):
    """Add two integers asynchronously."""

    @property
    def name(self) -> str:
        return "async_add"

    @property
    def description(self) -> str:
        return "Add two integers asynchronously."

    @property
    def input_model(self) -> type[AddInput]:
        return AddInput

    @property
    def output_model(self) -> type[AddOutput]:
        return AddOutput

    async def execute(self, **arguments: Any) -> dict[str, int]:
        return {"result": int(arguments["left"]) + int(arguments["right"])}
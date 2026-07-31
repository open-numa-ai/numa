"""Inspect and execute a schema-backed tool through the runtime."""

from pprint import pprint

from numa import AgentRuntime
from numa.tools import AddTool


def main() -> None:
    """Register, inspect, and execute the deterministic AddTool."""
    runtime = AgentRuntime()
    tool = AddTool()
    runtime.register_tool(tool)

    pprint(tool.input_schema)
    print(runtime.execute_tool("add", left=2, right=3))


if __name__ == "__main__":
    main()

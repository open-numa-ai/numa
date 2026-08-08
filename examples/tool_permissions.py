"""Restrict Runtime-managed Tool execution with an explicit allowlist."""

from numa import AgentRuntime, ToolAllowlistPolicy
from numa.tools import AddTool

runtime = AgentRuntime(tool_permission_policy=ToolAllowlistPolicy(["add"]))
runtime.register_tool(AddTool())

print(runtime.execute_tool("add", left=2, right=3))

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from pytest import MonkeyPatch

from numa.agents import Agent
from numa.core import Context, Message, MessageRole, Task
from numa.plugins import (
    AGENT_PLUGIN_GROUP,
    TOOL_PLUGIN_GROUP,
    PluginConflictError,
    PluginLoadError,
    PluginTypeError,
    discover_agents,
    discover_tools,
)
from numa.tools import Tool


class ExternalAgent(Agent):
    @property
    def name(self) -> str:
        return "external"

    def run(self, task: Task, context: Context) -> Message:
        del context
        return Message(role=MessageRole.ASSISTANT, content=task.description)


class ExternalTool(Tool):
    @property
    def name(self) -> str:
        return "external_tool"

    def execute(self, **arguments: Any) -> str:
        del arguments
        return "done"


@dataclass
class FakeEntryPoint:
    name: str
    loaded: object

    def load(self) -> object:
        if isinstance(self.loaded, Exception):
            raise self.loaded
        return self.loaded


def set_entry_points(monkeypatch: MonkeyPatch, *points: FakeEntryPoint) -> None:
    def fake_entry_points(*, group: str) -> list[FakeEntryPoint]:
        if group == AGENT_PLUGIN_GROUP:
            return list(points)
        return []

    monkeypatch.setattr("numa.plugins.discovery.entry_points", fake_entry_points)


def test_discovers_builtin_plugins(monkeypatch: MonkeyPatch) -> None:
    set_entry_points(monkeypatch)

    assert discover_agents()["example_agent"].load().name == "example_agent"
    assert discover_tools()["add"].load().name == "add"


def test_entry_point_is_loaded_lazily(monkeypatch: MonkeyPatch) -> None:
    load_count = 0

    def factory() -> ExternalAgent:
        nonlocal load_count
        load_count += 1
        return ExternalAgent()

    set_entry_points(monkeypatch, FakeEntryPoint("external", factory))

    plugin = discover_agents()["external"]

    assert load_count == 0
    assert plugin.load().name == "external"
    assert load_count == 1


def test_discovers_external_tool(monkeypatch: MonkeyPatch) -> None:
    def fake_entry_points(*, group: str) -> list[FakeEntryPoint]:
        if group == TOOL_PLUGIN_GROUP:
            return [FakeEntryPoint("external_tool", ExternalTool)]
        return []

    monkeypatch.setattr("numa.plugins.discovery.entry_points", fake_entry_points)

    assert discover_tools()["external_tool"].load().name == "external_tool"


def test_failed_plugin_does_not_prevent_loading_another(monkeypatch: MonkeyPatch) -> None:
    set_entry_points(
        monkeypatch,
        FakeEntryPoint("broken", RuntimeError("import failed")),
        FakeEntryPoint("external", ExternalAgent),
    )

    plugins = discover_agents()

    assert plugins["external"].load().name == "external"
    with pytest.raises(PluginLoadError, match="broken"):
        plugins["broken"].load()


@pytest.mark.parametrize("loaded", [object(), lambda: object()])
def test_rejects_invalid_plugin_factory(monkeypatch: MonkeyPatch, loaded: Any) -> None:
    set_entry_points(monkeypatch, FakeEntryPoint("invalid", loaded))

    with pytest.raises(PluginTypeError, match="invalid"):
        discover_agents()["invalid"].load()


def test_rejects_component_name_mismatch(monkeypatch: MonkeyPatch) -> None:
    set_entry_points(monkeypatch, FakeEntryPoint("different", ExternalAgent))

    with pytest.raises(PluginTypeError, match="created a component named"):
        discover_agents()["different"].load()


def test_rejects_duplicate_plugin_name(monkeypatch: MonkeyPatch) -> None:
    set_entry_points(monkeypatch, FakeEntryPoint("example_agent", ExternalAgent))

    with pytest.raises(PluginConflictError, match="example_agent"):
        discover_agents()

"""Entry-point discovery for external Agent and Tool plugins."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from importlib.metadata import entry_points
from typing import Generic, TypeVar, cast

from numa.agents import Agent, EchoAgent
from numa.plugins.exceptions import PluginConflictError, PluginLoadError, PluginTypeError
from numa.tools import AddTool, Tool

AGENT_PLUGIN_GROUP = "numa.agents"
TOOL_PLUGIN_GROUP = "numa.tools"

PluginComponent = TypeVar("PluginComponent", Agent, Tool)


@dataclass(frozen=True, slots=True)
class Plugin(Generic[PluginComponent]):
    """A lazily loaded plugin registered under a stable name."""

    name: str
    group: str
    component_type: type[PluginComponent]
    _load_factory: Callable[[], object] = field(repr=False)

    def load(self) -> PluginComponent:
        """Load the factory, create its component, and validate the contract."""
        try:
            factory = self._load_factory()
        except Exception as exc:
            raise PluginLoadError(f"Could not load plugin {self.name!r}") from exc

        if not callable(factory):
            raise PluginTypeError(f"Plugin {self.name!r} does not expose a factory")

        try:
            component = factory()
        except Exception as exc:
            raise PluginLoadError(f"Plugin {self.name!r} factory failed") from exc

        if not isinstance(component, self.component_type):
            expected = self.component_type.__name__
            raise PluginTypeError(f"Plugin {self.name!r} must create a {expected}")
        if component.name != self.name:
            raise PluginTypeError(
                f"Plugin {self.name!r} created a component named {component.name!r}"
            )
        return component


def discover_agents() -> dict[str, Plugin[Agent]]:
    """Discover built-in and installed Agent plugins."""
    return _discover(AGENT_PLUGIN_GROUP, Agent, {"example_agent": EchoAgent})  # type: ignore[type-abstract]


def discover_tools() -> dict[str, Plugin[Tool]]:
    """Discover built-in and installed Tool plugins."""
    return _discover(TOOL_PLUGIN_GROUP, Tool, {"add": AddTool})  # type: ignore[type-abstract]


def _discover(
    group: str,
    component_type: type[PluginComponent],
    builtins: Mapping[str, Callable[[], PluginComponent]],
) -> dict[str, Plugin[PluginComponent]]:
    def _builtin_loader(f: Callable[[], PluginComponent]) -> Callable[[], object]:
        def _loader() -> object:
            return f

        return _loader

    plugins = {
        name: Plugin(
            name=name,
            group=group,
            component_type=component_type,
            _load_factory=_builtin_loader(factory),
        )
        for name, factory in builtins.items()
    }

    for entry_point in entry_points(group=group):
        if entry_point.name in plugins:
            raise PluginConflictError(
                f"Plugin {entry_point.name!r} is registered more than once in {group!r}"
            )
        plugins[entry_point.name] = Plugin(
            name=entry_point.name,
            group=group,
            component_type=component_type,
            _load_factory=cast(Callable[[], object], entry_point.load),
        )
    return plugins

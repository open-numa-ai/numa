"""Exceptions raised while discovering and loading Numa plugins."""

from numa.core import NumaError


class PluginError(NumaError):
    """Base class for plugin discovery and loading errors."""


class PluginConflictError(PluginError):
    """Raised when multiple plugins register the same name."""


class PluginLoadError(PluginError):
    """Raised when a plugin factory cannot be loaded or invoked."""


class PluginNotFoundError(PluginError):
    """Raised when a requested plugin is not installed."""


class PluginTypeError(PluginError):
    """Raised when a plugin factory returns an invalid component."""

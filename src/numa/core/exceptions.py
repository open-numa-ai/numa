"""Exception hierarchy for stable error handling across Numa."""


class NumaError(Exception):
    """Base class for all framework-specific exceptions."""


class ConfigurationError(NumaError):
    """Raised when configuration cannot be loaded or validated."""


class AgentExecutionError(NumaError):
    """Raised when an agent cannot complete a task."""


class ToolExecutionError(NumaError):
    """Raised when a tool invocation fails."""


class MemoryError(NumaError):
    """Raised when a memory operation fails."""

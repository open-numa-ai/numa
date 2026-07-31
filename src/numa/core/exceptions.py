"""Exception hierarchy for stable error handling across Numa."""


class NumaError(Exception):
    """Base class for all framework-specific exceptions."""


class ConfigurationError(NumaError):
    """Raised when configuration cannot be loaded or validated."""


class AgentExecutionError(NumaError):
    """Raised when an agent cannot complete a task."""


class AgentTimeoutError(AgentExecutionError):
    """Raised when an Agent exceeds its configured execution timeout."""


class ToolExecutionError(NumaError):
    """Raised when a tool invocation fails."""


class ToolTimeoutError(ToolExecutionError):
    """Raised when a Tool exceeds its configured execution timeout."""


class ToolNotFoundError(NumaError):
    """Raised when a requested tool is not registered."""


class ToolValidationError(NumaError):
    """Raised when tool input or output violates its declared schema."""


class MemoryError(NumaError):
    """Raised when a memory operation fails."""

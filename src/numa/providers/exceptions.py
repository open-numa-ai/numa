"""Exceptions raised by model provider adapters."""

from numa.core import NumaError


class ModelProviderError(NumaError):
    """Base class for model provider failures."""


class ModelProviderConfigurationError(ModelProviderError):
    """Raised when a provider is missing required configuration."""


class ModelProviderExecutionError(ModelProviderError):
    """Raised when a provider cannot complete a model request."""

"""Explicit resilience policies for asynchronous Runtime execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Configure bounded retries with deterministic exponential backoff."""

    max_attempts: int = 1
    delay_seconds: float = 0.0
    backoff_multiplier: float = 1.0
    max_delay_seconds: float | None = None
    retry_exceptions: tuple[type[Exception], ...] = (Exception,)

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if not isfinite(self.delay_seconds) or self.delay_seconds < 0:
            raise ValueError("delay_seconds must be finite and non-negative")
        if not isfinite(self.backoff_multiplier) or self.backoff_multiplier < 1:
            raise ValueError("backoff_multiplier must be finite and at least 1")
        if self.max_delay_seconds is not None and (
            not isfinite(self.max_delay_seconds) or self.max_delay_seconds < 0
        ):
            raise ValueError("max_delay_seconds must be finite and non-negative")
        if not self.retry_exceptions:
            raise ValueError("retry_exceptions cannot be empty")
        if any(
            not isinstance(exception_type, type) or not issubclass(exception_type, Exception)
            for exception_type in self.retry_exceptions
        ):
            raise ValueError("retry_exceptions must contain Exception types")

    def delay_before_attempt(self, attempt: int) -> float:
        """Return the delay before a one-based retry attempt."""
        if attempt <= 1:
            return 0.0
        delay = self.delay_seconds * self.backoff_multiplier ** (attempt - 2)
        if self.max_delay_seconds is not None:
            return min(delay, self.max_delay_seconds)
        return delay

    def should_retry(self, exc: Exception, attempt: int) -> bool:
        """Return whether an exception should trigger another attempt."""
        return attempt < self.max_attempts and isinstance(exc, self.retry_exceptions)


@dataclass(frozen=True, slots=True)
class ResiliencePolicy:
    """Combine a total execution timeout with a retry policy."""

    timeout_seconds: float | None = None
    retry: RetryPolicy = field(default_factory=RetryPolicy)

    def __post_init__(self) -> None:
        if self.timeout_seconds is not None and (
            not isfinite(self.timeout_seconds) or self.timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds must be finite and greater than 0")

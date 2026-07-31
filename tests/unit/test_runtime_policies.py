import pytest

from numa.runtime import ResiliencePolicy, RetryPolicy


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"max_attempts": 0}, "max_attempts"),
        ({"delay_seconds": -1}, "delay_seconds"),
        ({"backoff_multiplier": 0.5}, "backoff_multiplier"),
        ({"max_delay_seconds": -1}, "max_delay_seconds"),
        ({"retry_exceptions": ()}, "retry_exceptions"),
        ({"retry_exceptions": (KeyboardInterrupt,)}, "retry_exceptions"),
        ({"retry_exceptions": ("ValueError",)}, "retry_exceptions"),
        ({"delay_seconds": float("nan")}, "delay_seconds"),
    ],
)
def test_retry_policy_rejects_invalid_values(
    arguments: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        RetryPolicy(**arguments)  # type: ignore[arg-type]


def test_retry_policy_calculates_capped_exponential_backoff() -> None:
    policy = RetryPolicy(
        max_attempts=5,
        delay_seconds=0.5,
        backoff_multiplier=2,
        max_delay_seconds=1.5,
    )

    assert [policy.delay_before_attempt(attempt) for attempt in range(1, 6)] == [
        0.0,
        0.5,
        1.0,
        1.5,
        1.5,
    ]


def test_resilience_policy_rejects_non_positive_timeout() -> None:
    with pytest.raises(ValueError, match="timeout_seconds"):
        ResiliencePolicy(timeout_seconds=0)

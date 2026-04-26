"""Domain service for webhook delivery retry scheduling."""

import random
from datetime import datetime, timedelta


def calculate_retry_delay(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter_factor: float = 0.1,
) -> float:
    """
    Calculate the delay before the next retry attempt.

    Uses capped exponential backoff with bounded jitter so a large retry batch
    does not stampede the same subscriber at the same second.
    """
    if base_delay <= 0:
        raise ValueError("base_delay must be greater than zero")
    if max_delay <= 0:
        raise ValueError("max_delay must be greater than zero")
    if jitter_factor < 0:
        raise ValueError("jitter_factor cannot be negative")

    normalized_attempt = max(1, attempt)
    exponential_delay = base_delay * (2 ** (normalized_attempt - 1))
    capped_delay = min(exponential_delay, max_delay)

    jitter_range = capped_delay * jitter_factor
    jitter = random.uniform(-jitter_range, jitter_range)

    return max(0, capped_delay + jitter)


def get_next_retry_time(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter_factor: float = 0.1,
) -> datetime:
    """Get the datetime when the next retry should occur."""
    delay = calculate_retry_delay(attempt, base_delay, max_delay, jitter_factor)
    return datetime.utcnow() + timedelta(seconds=delay)


def should_retry(attempt: int, max_retries: int = 5) -> bool:
    """Return True when the current attempt is still retryable."""
    if max_retries < 0:
        raise ValueError("max_retries cannot be negative")
    return attempt < max_retries


def get_retry_schedule(
    max_retries: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter_factor: float = 0.1,
) -> list:
    """Get the full retry schedule for diagnostics and tests."""
    return [
        calculate_retry_delay(i, base_delay, max_delay, jitter_factor)
        for i in range(1, max_retries + 1)
    ]

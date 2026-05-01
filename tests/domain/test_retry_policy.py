from datetime import UTC, datetime

import pytest

from domain.services.retry_policy import (
    calculate_retry_delay,
    get_next_retry_time,
    should_retry,
)


def test_calculate_retry_delay_exponential_without_jitter():
    assert calculate_retry_delay(1, jitter_factor=0) == pytest.approx(1.0)
    assert calculate_retry_delay(2, jitter_factor=0) == pytest.approx(2.0)
    assert calculate_retry_delay(3, jitter_factor=0) == pytest.approx(4.0)


def test_calculate_retry_delay_caps_at_max_delay():
    assert calculate_retry_delay(10, max_delay=30, jitter_factor=0) == pytest.approx(30.0)


def test_should_retry_stops_at_max_retries():
    assert should_retry(1, max_retries=3) is True
    assert should_retry(3, max_retries=3) is False


def test_get_next_retry_time_returns_future_datetime():
    before = datetime.now(UTC)
    retry_at = get_next_retry_time(1, base_delay=1, max_delay=1, jitter_factor=0)

    assert retry_at > before

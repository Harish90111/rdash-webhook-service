"""Domain service for matching event types against subscription patterns."""

from fnmatch import fnmatchcase
from typing import List


def matches_wildcard(event_type: str, pattern: str) -> bool:
    """
    Check if an event type matches a subscription pattern.
    
    Matching is segment-aware: event types are split on "." and each wildcard
    segment matches one event segment. This keeps "po.*" from accidentally
    matching "po.created.v2"; use "po.*.*" for that shape.

    Supported wildcards inside a segment:
    - "*" matches any characters in one segment
    - "?" matches any single character in one segment
    - exact matches also work
    
    Args:
        event_type: The actual event type (e.g., 'po.created')
        pattern: The subscription pattern (e.g., 'po.*')
    
    Returns:
        True if the event type matches the pattern, False otherwise
    """
    if not event_type or not pattern:
        return False
    
    if event_type == pattern:
        return True

    event_segments = event_type.split(".")
    pattern_segments = pattern.split(".")
    if len(event_segments) != len(pattern_segments):
        return False

    return all(
        fnmatchcase(event_segment, pattern_segment)
        for event_segment, pattern_segment in zip(event_segments, pattern_segments)
    )


def match_subscriptions(event_type: str, subscription_patterns: List[str]) -> List[str]:
    """
    Find all patterns that match an event type.
    
    Args:
        event_type: The actual event type
        subscription_patterns: List of subscription patterns
    
    Returns:
        List of patterns that match the event type
    """
    return [pattern for pattern in subscription_patterns if matches_wildcard(event_type, pattern)]


if __name__ == "__main__":
    assert matches_wildcard("po.created", "po.*") is True
    assert matches_wildcard("po.approved", "po.*") is True
    assert matches_wildcard("order.created", "po.*") is False
    assert matches_wildcard("po.created", "po.created") is True
    assert matches_wildcard("po.created", "order.*") is False
    assert matches_wildcard("order.created.v2", "order.*.*") is True
    assert matches_wildcard("po.created.v2", "po.*") is False
    assert matches_wildcard("po.c", "po.?") is True
    assert matches_wildcard("po.created", "po.?") is False

    print("All wildcard matching tests passed!")

from domain.services.wildcard_matching import match_subscriptions, matches_wildcard


def test_wildcard_matches_one_event_segment():
    assert matches_wildcard("po.created", "po.*") is True
    assert matches_wildcard("po.approved", "po.*") is True


def test_wildcard_does_not_cross_segment_boundaries():
    assert matches_wildcard("po.created.v2", "po.*") is False
    assert matches_wildcard("po.created.v2", "po.*.*") is True


def test_question_mark_matches_single_character_in_segment():
    assert matches_wildcard("po.c", "po.?") is True
    assert matches_wildcard("po.created", "po.?") is False


def test_match_subscriptions_returns_matching_patterns():
    patterns = ["po.*", "invoice.*", "po.created"]

    assert match_subscriptions("po.created", patterns) == ["po.*", "po.created"]

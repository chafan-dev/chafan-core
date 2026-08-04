"""Pins that the policy table reproduces the behavior it consolidated.

These are equivalence tests, not specification tests. They encode what the
scattered constants and branches did *before* the table existed, so that this
consolidation can be reviewed as behavior-neutral. When a later change
deliberately alters a rule, the expectation here is meant to change with it.
"""

from chafan_core.app.services.activity_policy import (
    ALWAYS_PUBLIC_EVENT_VERBS,
    POLICY,
    Audience,
)

# Verbatim from feed_impl.ALWAYS_PUBLIC_EVENT_VERBS before consolidation.
_LEGACY_ALWAYS_PUBLIC = {
    "create_article",
    "comment_article",
    "upvote_article",
    "follow_article_column",
}

# The only verbs that are fanned out. Everything else writes an Activity (or
# not) but never reaches a Feed row.
_FANNED_OUT = {"create_question", "answer_question", "create_article"}


def test_always_public_verbs_unchanged() -> None:
    assert set(ALWAYS_PUBLIC_EVENT_VERBS) == _LEGACY_ALWAYS_PUBLIC


def test_fanned_out_verbs_reach_subject_followers() -> None:
    """Every fanned-out verb still reaches the audience v1 delivered to."""
    for verb in _FANNED_OUT:
        assert Audience.SUBJECT_FOLLOWERS in POLICY[verb].feed_audience, verb


def test_create_article_also_reaches_column_subscribers() -> None:
    """3b-2: subscribers used to get a notification with no feed row to match."""
    assert POLICY["create_article"].feed_audience == (
        Audience.SUBJECT_FOLLOWERS,
        Audience.ARTICLE_COLUMN_SUBSCRIBERS,
    )
    assert Audience.ARTICLE_COLUMN_SUBSCRIBERS in POLICY["create_article"].notifies


def test_other_verbs_have_no_feed_audience() -> None:
    """No verb gains a fan-out it did not have before."""
    for verb, policy in POLICY.items():
        if verb in _FANNED_OUT:
            continue
        assert policy.feed_audience == (), verb


def test_every_policy_is_keyed_by_its_own_verb() -> None:
    for verb, policy in POLICY.items():
        assert policy.verb == verb


def test_verbs_without_emitter_deliver_nothing() -> None:
    """A verb with no live emitter must not claim any sink.

    These exist only so rows already persisted keep materializing; if one ever
    grows an emitter, its policy has to be filled in at the same time.
    """
    for verb, policy in POLICY.items():
        if policy.emitted_by:
            continue
        assert not policy.writes_activity, verb
        assert policy.feed_audience == (), verb
        assert policy.notifies == (), verb
        assert not policy.pays_coins, verb

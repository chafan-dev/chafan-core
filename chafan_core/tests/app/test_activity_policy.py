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
    feed_audience_of,
)

# Verbatim from feed_impl.ALWAYS_PUBLIC_EVENT_VERBS before consolidation.
_LEGACY_ALWAYS_PUBLIC = {
    "create_article",
    "comment_article",
    "upvote_article",
    "follow_article_column",
}

# The only verbs whose Activity reaches new_activity_into_feed today, i.e. the
# three postprocess paths that call it. Everything else writes an Activity (or
# not) but is never fanned out.
_LEGACY_FANNED_OUT = {"create_question", "answer_question", "create_article"}


def test_always_public_verbs_unchanged() -> None:
    assert set(ALWAYS_PUBLIC_EVENT_VERBS) == _LEGACY_ALWAYS_PUBLIC


def test_fanned_out_verbs_resolve_to_subject_followers() -> None:
    """The pre-consolidation fan-out delivered to the subject's followers."""
    for verb in _LEGACY_FANNED_OUT:
        assert feed_audience_of(verb) is Audience.SUBJECT_FOLLOWERS, verb


def test_other_verbs_have_no_feed_audience() -> None:
    """No verb gains a fan-out it did not have before."""
    for verb, policy in POLICY.items():
        if verb in _LEGACY_FANNED_OUT:
            continue
        assert policy.feed_audience is None, verb


def test_unknown_verb_has_no_feed_audience() -> None:
    assert feed_audience_of("no_such_verb") is None


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
        assert policy.feed_audience is None, verb
        assert policy.notifies == (), verb
        assert not policy.pays_coins, verb

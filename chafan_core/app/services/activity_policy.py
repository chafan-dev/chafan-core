"""Per-verb policy for domain events: what gets written, and who receives it.

Background
----------
Every user-visible thing that happens on Chafan is described by an
:class:`~chafan_core.app.schemas.event.EventInternal` — an immutable fact such
as "user 3 answered question 7 at T". That one event can end up in as many as
four sinks:

``Activity``
    The publishable event log. One row carries the serialized event plus the
    site it may be seen in.
``Feed``
    A delivery record: ``(activity_id, receiver_id)``. N rows per Activity, one
    per recipient. Written by fan-out at publication time.
``Notification``
    A *directed* delivery to one receiver, with read/delivered state and a push
    side effect. Re-serializes the event rather than referencing the Activity.
``CoinPayment.event_json``
    The event as the *reason* for a coin transfer.

Until now, the rules governing those four sinks lived in four disconnected
places: the (dead) ``feed_impl.get_activity_dist_info``, the followers-only
``feed_impl.lookup_activity_receiver_list`` (both since deleted), ``feed_impl``'s
``ALWAYS_PUBLIC_EVENT_VERBS``, and 21 hand-written ``create_with_content``
call sites spread over ``crud_message`` and six ``services`` modules. Nothing
enforced that a verb was handled consistently, or handled at all.

:data:`POLICY` is that knowledge in one place.

What is authoritative here, and what is only recorded
-----------------------------------------------------
This module is deliberately split between fields that *drive* behavior and
fields that merely *describe* it.

Authoritative — the code reads these and behaves accordingly:

* :attr:`EventPolicy.feed_audience` — ``events.distribute``.
* :attr:`EventPolicy.always_public` — ``feed_impl._is_public_activity``.
* :attr:`EventPolicy.writes_activity`, :attr:`EventPolicy.notifies` and
  :attr:`EventPolicy.notify_exclusions` — ``events.distribute``.

Descriptive — an audit of the call sites, read by nobody at runtime. They
exist so the next change has a map instead of a grep, and so drift is visible
in review:

* :attr:`EventPolicy.pays_coins`, :attr:`EventPolicy.emitted_by`.

Recorded but not applied:

* :attr:`EventPolicy.unapplied_feed_audience` and
  :attr:`EventPolicy.unapplied_exclusions` preserve the audience rules from
  ``get_activity_dist_info``, the v1 fan-out that this change deletes. That
  function was unreferenced, so those rules are **not** in force today: the
  live fan-out delivers to the subject's followers and nobody else. They are
  kept because they encode intent that was expensive to work out and would
  otherwise be lost with the code.

Every verb reachable through ``EventInternal`` must appear in :data:`POLICY`;
``scripts/check.py`` fails the build otherwise.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Mapping, Optional, Tuple


class Audience(enum.Enum):
    """A group of users resolved from an event, relative to its subject."""

    #: Everyone following the user who caused the event.
    SUBJECT_FOLLOWERS = "subject_followers"
    #: Members of the site the event happened in.
    SITE_MEMBERS = "site_members"
    #: The moderator of the site the event refers to.
    SITE_MODERATOR = "site_moderator"
    #: The instance superuser.
    SUPERUSER = "superuser"
    #: Author of the question the event refers to.
    QUESTION_AUTHOR = "question_author"
    #: Users subscribed to the question the event refers to.
    QUESTION_SUBSCRIBERS = "question_subscribers"
    #: Author of the answer the event refers to.
    ANSWER_AUTHOR = "answer_author"
    #: Users who bookmarked the answer the event refers to.
    ANSWER_BOOKMARKERS = "answer_bookmarkers"
    #: Author of the article the event refers to.
    ARTICLE_AUTHOR = "article_author"
    #: Subscribers of the article column the event refers to.
    ARTICLE_COLUMN_SUBSCRIBERS = "article_column_subscribers"
    #: Author of the submission the event refers to.
    SUBMISSION_AUTHOR = "submission_author"
    #: Author of the comment being replied to.
    PARENT_COMMENT_AUTHOR = "parent_comment_author"
    #: Users @-mentioned in the comment body.
    MENTIONED_USERS = "mentioned_users"
    #: Members of the message channel, excluding the sender.
    CHANNEL_MEMBERS = "channel_members"
    #: The user named by the event (invitee, followee, ...).
    TARGET_USER = "target_user"
    #: The user a reward was created for.
    REWARD_RECEIVER = "reward_receiver"
    #: The user who funded a reward.
    REWARD_GIVER = "reward_giver"


class Exclusion(enum.Enum):
    """A group subtracted from a resolved audience."""

    #: Never deliver an event back to whoever caused it.
    SUBJECT = "subject"
    #: Skip the author of the content acted upon.
    CONTENT_AUTHOR = "content_author"
    #: Skip users who already upvoted the same content.
    EXISTING_UPVOTERS = "existing_upvoters"
    #: Skip users already subscribed to the column.
    EXISTING_SUBSCRIBERS = "existing_subscribers"
    #: Skip users who already follow the user being followed.
    EXISTING_FOLLOWERS_OF_TARGET = "existing_followers_of_target"
    #: Skip the user named by the event.
    TARGET_USER = "target_user"


@dataclass(frozen=True)
class EventPolicy:
    """What the system does today with one verb, and what it was meant to do.

    See the module docstring for which fields drive behavior and which are a
    record of the current scattered implementation.
    """

    #: The ``verb`` discriminator of the event content model.
    verb: str

    # -- authoritative ----------------------------------------------------
    #: Audiences receiving a ``Feed`` row when this verb is fanned out, unioned.
    #: Empty means no fan-out happens for this verb today.
    feed_audience: Tuple[Audience, ...] = ()
    #: Visible in the random/discovery feed regardless of site readability.
    always_public: bool = False

    # -- descriptive ------------------------------------------------------
    #: Whether any code path writes an ``Activity`` row for this verb.
    writes_activity: bool = False
    #: Receivers of a ``Notification`` for this verb today.
    notifies: Tuple[Audience, ...] = ()
    #: Exclusions subtracted from :attr:`notifies`. Unlike
    #: :attr:`unapplied_exclusions` these *are* in force -- they reproduce the
    #: ``author_id != receiver_id`` guards the notification call sites apply.
    notify_exclusions: Tuple[Exclusion, ...] = ()
    #: Whether the event is used as a ``CoinPayment`` reason.
    pays_coins: bool = False
    #: Dotted references to the functions that construct this event. Empty
    #: means the verb has no live emitter: it survives only so that rows
    #: already in the database keep materializing.
    emitted_by: Tuple[str, ...] = ()

    # -- recorded, not applied --------------------------------------------
    #: Audiences ``get_activity_dist_info`` (v1, deleted) also delivered to.
    unapplied_feed_audience: Tuple[Audience, ...] = ()
    #: Exclusions ``get_activity_dist_info`` (v1, deleted) applied.
    unapplied_exclusions: Tuple[Exclusion, ...] = ()

    #: Free-text note about anything irregular in the current handling.
    note: str = ""


_POLICIES: Tuple[EventPolicy, ...] = (
    # -- content creation -------------------------------------------------
    EventPolicy(
        "create_question",
        writes_activity=True,
        feed_audience=(Audience.SUBJECT_FOLLOWERS,),
        emitted_by=("services.postprocess.postprocess_new_question",),
        unapplied_feed_audience=(Audience.SITE_MEMBERS,),
        unapplied_exclusions=(Exclusion.SUBJECT,),
    ),
    EventPolicy(
        "answer_question",
        writes_activity=True,
        feed_audience=(Audience.SUBJECT_FOLLOWERS,),
        notifies=(Audience.QUESTION_AUTHOR,),
        notify_exclusions=(Exclusion.SUBJECT,),
        emitted_by=("services.postprocess.postprocess_new_answer",),
        unapplied_feed_audience=(Audience.QUESTION_SUBSCRIBERS,),
        unapplied_exclusions=(Exclusion.SUBJECT,),
    ),
    EventPolicy(
        "create_article",
        writes_activity=True,
        feed_audience=(
            Audience.SUBJECT_FOLLOWERS,
            Audience.ARTICLE_COLUMN_SUBSCRIBERS,
        ),
        always_public=True,
        notifies=(Audience.ARTICLE_COLUMN_SUBSCRIBERS,),
        emitted_by=(
            "services.postprocess.postprocess_new_article",
            "services.postprocess.postprocess_updated_article",
        ),
        unapplied_exclusions=(Exclusion.SUBJECT,),
        note=(
            "Two emitters, one per publication route: created-published goes "
            "through postprocess_new_article, draft-then-published through "
            "postprocess_updated_article. They are mutually exclusive per "
            "article because is_published is never reverted, so a published "
            "article has exactly one Activity and a draft has none."
        ),
    ),
    EventPolicy(
        "create_submission",
        writes_activity=True,
        emitted_by=("crud.crud_submission.create_with_author",),
        unapplied_exclusions=(Exclusion.SUBJECT,),
        note="Activity is written but never fanned out (TODO in postprocess_new_submission).",
    ),
    # -- comments ---------------------------------------------------------
    EventPolicy(
        "comment_question",
        writes_activity=True,
        notifies=(Audience.QUESTION_AUTHOR,),
        notify_exclusions=(Exclusion.SUBJECT,),
        emitted_by=("services.postprocess.postprocess_new_comment",),
        note="Activity only when the comment is shared to timeline; never fanned out.",
    ),
    EventPolicy(
        "comment_answer",
        writes_activity=True,
        notifies=(Audience.ANSWER_AUTHOR,),
        notify_exclusions=(Exclusion.SUBJECT,),
        emitted_by=("services.postprocess.postprocess_new_comment",),
        note="Activity only when the comment is shared to timeline; never fanned out.",
    ),
    EventPolicy(
        "comment_article",
        writes_activity=True,
        always_public=True,
        notifies=(Audience.ARTICLE_AUTHOR,),
        notify_exclusions=(Exclusion.SUBJECT,),
        emitted_by=("services.postprocess.postprocess_new_comment",),
        note="Activity only when the comment is shared to timeline; never fanned out.",
    ),
    EventPolicy(
        "comment_submission",
        writes_activity=True,
        notifies=(Audience.SUBMISSION_AUTHOR,),
        notify_exclusions=(Exclusion.SUBJECT,),
        emitted_by=("services.postprocess.postprocess_new_comment",),
        note="Activity only when the comment is shared to timeline; never fanned out.",
    ),
    EventPolicy(
        "reply_comment",
        writes_activity=True,
        notifies=(Audience.PARENT_COMMENT_AUTHOR,),
        notify_exclusions=(Exclusion.SUBJECT,),
        emitted_by=("services.postprocess.postprocess_new_comment",),
        note="Activity only when the comment is shared to timeline; never fanned out.",
    ),
    EventPolicy(
        "mentioned_in_comment",
        notifies=(Audience.MENTIONED_USERS,),
        emitted_by=("services.postprocess.notify_mentioned_users",),
    ),
    # -- votes ------------------------------------------------------------
    EventPolicy(
        "upvote_answer",
        writes_activity=True,
        notifies=(Audience.ANSWER_AUTHOR,),
        pays_coins=True,
        emitted_by=(
            "crud.crud_answer.upvote",
            "services.answers.upvote_answer",
        ),
        unapplied_exclusions=(
            Exclusion.SUBJECT,
            Exclusion.EXISTING_UPVOTERS,
            Exclusion.CONTENT_AUTHOR,
        ),
    ),
    EventPolicy(
        "upvote_question",
        writes_activity=True,
        emitted_by=("crud.crud_question.upvote",),
        unapplied_exclusions=(
            Exclusion.SUBJECT,
            Exclusion.EXISTING_UPVOTERS,
            Exclusion.CONTENT_AUTHOR,
        ),
    ),
    EventPolicy(
        "upvote_article",
        writes_activity=True,
        always_public=True,
        emitted_by=("crud.crud_article.upvote",),
        unapplied_exclusions=(
            Exclusion.SUBJECT,
            Exclusion.EXISTING_UPVOTERS,
            Exclusion.CONTENT_AUTHOR,
        ),
    ),
    EventPolicy(
        "upvote_submission",
        writes_activity=True,
        emitted_by=("crud.crud_submission.upvote",),
        unapplied_exclusions=(Exclusion.SUBJECT,),
    ),
    # -- following / subscribing -----------------------------------------
    EventPolicy(
        "follow_user",
        writes_activity=True,
        notifies=(Audience.TARGET_USER,),
        emitted_by=("crud.crud_user.add_follower", "services.me.follow_user"),
        unapplied_exclusions=(
            Exclusion.SUBJECT,
            Exclusion.TARGET_USER,
            Exclusion.EXISTING_FOLLOWERS_OF_TARGET,
        ),
    ),
    EventPolicy(
        "follow_article_column",
        writes_activity=True,
        always_public=True,
        emitted_by=("crud.crud_user.subscribe_article_column",),
        unapplied_exclusions=(
            Exclusion.SUBJECT,
            Exclusion.EXISTING_SUBSCRIBERS,
            Exclusion.CONTENT_AUTHOR,
        ),
    ),
    # -- edits and suggestions -------------------------------------------
    EventPolicy(
        "edit_question",
        notifies=(Audience.QUESTION_AUTHOR,),
        notify_exclusions=(Exclusion.SUBJECT,),
        emitted_by=("services.postprocess.postprocess_updated_question",),
    ),
    EventPolicy(
        "answer_update",
        notifies=(Audience.ANSWER_BOOKMARKERS,),
        emitted_by=("services.postprocess.postprocess_new_answer",),
    ),
    EventPolicy(
        "create_submission_suggestion",
        notifies=(Audience.SUBMISSION_AUTHOR,),
        emitted_by=("services.postprocess.postprocess_new_submission_suggestion",),
    ),
    EventPolicy(
        "accept_submission_suggestion",
        note="No live emitter, and no karma: accepting a suggestion is not in rules.py.",
    ),
    EventPolicy(
        "create_answer_suggest_edit",
        notifies=(Audience.ANSWER_AUTHOR,),
        emitted_by=("services.postprocess.postprocess_new_answer_suggest_edit",),
    ),
    EventPolicy(
        "accept_answer_suggest_edit",
        note="No live emitter, and no karma: accepting a suggestion is not in rules.py.",
    ),
    # -- sites, invitations, messages -------------------------------------
    EventPolicy(
        "create_site",
        pays_coins=True,
        emitted_by=("services.sites.create_site",),
    ),
    EventPolicy(
        "create_site_need_approval",
        note="No live emitter: site creation is gated on karma, not approval. "
        "Kept so rows already persisted keep materializing.",
    ),
    EventPolicy(
        "apply_join_site",
        notifies=(Audience.SITE_MODERATOR,),
        emitted_by=("services.sites.apply_join_site",),
    ),
    EventPolicy(
        "invite_join_site",
        notifies=(Audience.TARGET_USER,),
        emitted_by=("services.users.invite_user_to_site",),
    ),
    EventPolicy(
        "invite_answer",
        notifies=(Audience.TARGET_USER,),
        emitted_by=("services.questions.invite_answer",),
    ),
    EventPolicy(
        "invite_new_user",
        pays_coins=True,
        emitted_by=("services.accounts.reward_inviter",),
    ),
    EventPolicy(
        "create_message",
        notifies=(Audience.CHANNEL_MEMBERS,),
        notify_exclusions=(Exclusion.SUBJECT,),
        emitted_by=("crud.crud_message.create_with_author",),
    ),
    # -- rewards ----------------------------------------------------------
    EventPolicy(
        "create_answer_question_reward",
        notifies=(Audience.REWARD_RECEIVER,),
        emitted_by=("services.rewards.create_reward",),
    ),
    EventPolicy(
        "claim_answer_question_reward",
        notifies=(Audience.REWARD_GIVER,),
        emitted_by=("services.rewards.claim_reward",),
    ),
    # -- no live emitter --------------------------------------------------
    # Retained so that rows already persisted with these verbs still
    # materialize. Nothing in the codebase constructs them.
    EventPolicy("site_broadcast", note="No live emitter."),
    EventPolicy("system_broadcast", note="No live emitter."),
    EventPolicy("system_send_invitation", note="No live emitter."),
    EventPolicy("invited_user_activated", note="No live emitter."),
)


POLICY: Mapping[str, EventPolicy] = {p.verb: p for p in _POLICIES}

assert len(POLICY) == len(_POLICIES), "duplicate verb in _POLICIES"


#: Verbs shown in the random/discovery feed even when their site is not
#: publicly readable. Derived from :data:`POLICY` so there is one source.
ALWAYS_PUBLIC_EVENT_VERBS: frozenset[str] = frozenset(
    p.verb for p in _POLICIES if p.always_public
)

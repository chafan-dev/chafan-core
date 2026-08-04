"""Event distribution: the one place an event reaches its sinks.

An event that has happened must reach every sink
:data:`~chafan_core.app.services.activity_policy.POLICY` says it belongs in.
:func:`distribute` is that one place. See ``docs/glossary.md`` for the
vocabulary and ``docs/proposals/2026-08-03-event-distribution.md`` for the
design.

Duty
----
Given an event that has already happened:

1. Look up the policy for its verb.
2. Write **exactly one** ``Activity``, if the verb is publishable.
3. Resolve the feed audience and write ``Feed`` rows.
4. Resolve the notification audiences, write ``Notification`` rows, push each.

Everything is derived from the event: the verb selects the policy row, and the
content's ids resolve the site, the feed audience and the notification
receivers. Nothing about routing is passed in, so no caller can get it wrong.

Not its duty
------------
It never commits and never spawns a background task -- it writes into the
caller's session, so timing stays a property of the caller. It does not perform
the domain write, does not decide *whether* an event occurred (conditions like
``was_published`` are domain state and stay in the caller), does not touch
``CoinPayment``, and does not deduplicate: one call, one Activity.

Delivery is not visibility. A ``Feed`` row grants nothing -- ``materialize_*``
runs the full responder permission check per receiver at read time. A wrong
audience yields an item that silently does not render, not a leak.

Failure is contained. Because it writes into the caller's transaction, a
delivery problem here -- an audience that cannot be resolved, a Redis push that
fails -- is logged and skipped rather than raised, so it cannot roll back the
domain writes the caller already made. See :func:`_resolve`.
"""

from __future__ import annotations

import datetime
import enum
import logging
from typing import Callable, Dict, FrozenSet, Optional, Set

from chafan_core.app import crud, models
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.mq import push_notification
from chafan_core.app.schemas import event as ev
from chafan_core.app.schemas.event import EventInternal
from chafan_core.app.schemas.notification import NotificationCreate
from chafan_core.app.services.activity_policy import POLICY, Audience, Exclusion

logger = logging.getLogger(__name__)


class Sink(enum.Enum):
    """One of the three destinations :func:`distribute` writes to."""

    ACTIVITY = "activity"
    FEED = "feed"
    NOTIFICATION = "notification"


ALL_SINKS: FrozenSet[Sink] = frozenset(Sink)


# --------------------------------------------------------------------------
# Locators: find the domain object an event content refers to.
#
# A content model carries only ids, and different verbs reach the same object
# by different routes -- QUESTION_AUTHOR is reachable from `question_id` on a
# comment event and from `answer_id` on an answer event. These normalize that.
# --------------------------------------------------------------------------


def _attr(content: object, name: str) -> Optional[int]:
    value = getattr(content, name, None)
    return value if isinstance(value, int) else None


def _question_of(ctx: RequestContext, c: object) -> Optional[models.Question]:
    db = ctx.get_db()
    qid = _attr(c, "question_id")
    if qid is not None:
        return crud.question.get(db, id=qid)
    answer = _answer_of(ctx, c)
    return answer.question if answer is not None else None


def _answer_of(ctx: RequestContext, c: object) -> Optional[models.Answer]:
    db = ctx.get_db()
    aid = _attr(c, "answer_id")
    if aid is not None:
        return crud.answer.get(db, id=aid)
    sid = _attr(c, "answer_suggest_edit_id")
    if sid is not None:
        suggest = crud.answer_suggest_edit.get(db, id=sid)
        return suggest.answer if suggest is not None else None
    return None


def _submission_of(ctx: RequestContext, c: object) -> Optional[models.Submission]:
    db = ctx.get_db()
    sid = _attr(c, "submission_id")
    if sid is not None:
        return crud.submission.get(db, id=sid)
    ssid = _attr(c, "submission_suggestion_id")
    if ssid is not None:
        suggestion = crud.submission_suggestion.get(db, id=ssid)
        return suggestion.submission if suggestion is not None else None
    return None


def _article_of(ctx: RequestContext, c: object) -> Optional[models.Article]:
    aid = _attr(c, "article_id")
    return crud.article.get(ctx.get_db(), id=aid) if aid is not None else None


def _comment_of(ctx: RequestContext, c: object) -> Optional[models.Comment]:
    """The comment an event is *about* -- for a reply that is the reply itself."""
    db = ctx.get_db()
    cid = _attr(c, "comment_id")
    if cid is None:
        cid = _attr(c, "reply_id")
    return crud.comment.get(db, id=cid) if cid is not None else None


# --------------------------------------------------------------------------
# Site derivation. Reproduces the site_id each call site passed by hand.
# --------------------------------------------------------------------------


def _site_id_of(ctx: RequestContext, c: object) -> Optional[int]:
    if isinstance(c, (ev.CreateQuestionInternal, ev.UpvoteQuestionInternal)):
        question = _question_of(ctx, c)
        return question.site_id if question is not None else None
    if isinstance(c, (ev.AnswerQuestionInternal, ev.UpvoteAnswerInternal)):
        answer = _answer_of(ctx, c)
        return answer.site_id if answer is not None else None
    if isinstance(c, (ev.CreateSubmissionInternal, ev.UpvoteSubmissionInternal)):
        submission = _submission_of(ctx, c)
        return submission.site_id if submission is not None else None
    if isinstance(
        c,
        (
            ev.CommentQuestionInternal,
            ev.CommentAnswerInternal,
            ev.CommentArticleInternal,
            ev.CommentSubmissionInternal,
            ev.ReplyCommentInternal,
        ),
    ):
        comment = _comment_of(ctx, c)
        return comment.site_id if comment is not None else None
    # Articles, follows and column subscriptions are not site-scoped.
    return None


# --------------------------------------------------------------------------
# Audience resolvers.
# --------------------------------------------------------------------------


def _subject_followers(ctx: RequestContext, c: object) -> Set[int]:
    subject_id = _attr(c, "subject_id")
    if subject_id is None:
        return set()
    subject = crud.user.get(ctx.get_db(), id=subject_id)
    if subject is None:
        return set()
    return {follower.id for follower in subject.followers}


def _question_author(ctx: RequestContext, c: object) -> Set[int]:
    question = _question_of(ctx, c)
    return {question.author_id} if question is not None else set()


def _answer_author(ctx: RequestContext, c: object) -> Set[int]:
    answer = _answer_of(ctx, c)
    return {answer.author_id} if answer is not None else set()


def _article_author(ctx: RequestContext, c: object) -> Set[int]:
    article = _article_of(ctx, c)
    return {article.author_id} if article is not None else set()


def _submission_author(ctx: RequestContext, c: object) -> Set[int]:
    submission = _submission_of(ctx, c)
    return {submission.author_id} if submission is not None else set()


def _parent_comment_author(ctx: RequestContext, c: object) -> Set[int]:
    pid = _attr(c, "parent_comment_id")
    if pid is None:
        return set()
    parent = crud.comment.get(ctx.get_db(), id=pid)
    return {parent.author_id} if parent is not None else set()


def _answer_bookmarkers(ctx: RequestContext, c: object) -> Set[int]:
    answer = _answer_of(ctx, c)
    if answer is None:
        return set()
    return {user.id for user in answer.bookmarkers}


def _article_column_subscribers(ctx: RequestContext, c: object) -> Set[int]:
    article = _article_of(ctx, c)
    if article is None:
        return set()
    return {user.id for user in article.article_column.subscribers}


def _channel_members(ctx: RequestContext, c: object) -> Set[int]:
    cid = _attr(c, "channel_id")
    if cid is None:
        return set()
    channel = crud.channel.get(ctx.get_db(), id=cid)
    if channel is None:
        return set()
    return {member.id for member in channel.members}


def _target_user(ctx: RequestContext, c: object) -> Set[int]:
    uid = _attr(c, "user_id")
    return {uid} if uid is not None else set()


def _site_moderator(ctx: RequestContext, c: object) -> Set[int]:
    sid = _attr(c, "site_id")
    if sid is None:
        return set()
    site = crud.site.get(ctx.get_db(), id=sid)
    if site is None or site.moderator_id is None:
        return set()
    return {site.moderator_id}


def _superuser(ctx: RequestContext, c: object) -> Set[int]:
    superuser = crud.user.try_get_superuser(ctx.get_db())
    if superuser is None:
        logger.warning("no superuser; delivering to nobody")
        return set()
    return {superuser.id}


def _reward_receiver(ctx: RequestContext, c: object) -> Set[int]:
    rid = _attr(c, "reward_id")
    if rid is None:
        return set()
    reward = crud.reward.get(ctx.get_db(), id=rid)
    return {reward.receiver_id} if reward is not None else set()


def _reward_giver(ctx: RequestContext, c: object) -> Set[int]:
    rid = _attr(c, "reward_id")
    if rid is None:
        return set()
    reward = crud.reward.get(ctx.get_db(), id=rid)
    return {reward.giver_id} if reward is not None else set()


_RESOLVERS: Dict[Audience, Callable[[RequestContext, object], Set[int]]] = {
    Audience.SUBJECT_FOLLOWERS: _subject_followers,
    Audience.QUESTION_AUTHOR: _question_author,
    Audience.ANSWER_AUTHOR: _answer_author,
    Audience.ARTICLE_AUTHOR: _article_author,
    Audience.SUBMISSION_AUTHOR: _submission_author,
    Audience.PARENT_COMMENT_AUTHOR: _parent_comment_author,
    Audience.ANSWER_BOOKMARKERS: _answer_bookmarkers,
    Audience.ARTICLE_COLUMN_SUBSCRIBERS: _article_column_subscribers,
    Audience.CHANNEL_MEMBERS: _channel_members,
    Audience.TARGET_USER: _target_user,
    Audience.SITE_MODERATOR: _site_moderator,
    Audience.SUPERUSER: _superuser,
    Audience.REWARD_RECEIVER: _reward_receiver,
    Audience.REWARD_GIVER: _reward_giver,
}
# Audience.MENTIONED_USERS is intentionally absent: the handles come from the
# request payload, not the event, so `postprocess.notify_mentioned_users` keeps
# doing that one directly. Audience.SITE_MEMBERS and QUESTION_SUBSCRIBERS are
# recorded on the table as v1 rules that are not in force.


def _resolve(ctx: RequestContext, audience: Audience, content: object) -> Set[int]:
    """Resolve an audience to receiver ids, degrading to nobody on failure.

    A resolver walks relationships that the event's ids only *probably* reach:
    a deleted column, a site with no moderator, a superuser row that is missing
    in this deployment. None of that should propagate, because ``distribute``
    writes into the caller's transaction -- an audience that cannot be resolved
    would otherwise roll back the domain-adjacent writes the caller already
    made, such as the reputation award and webhook delivery that precede
    ``distribute`` in ``postprocess_new_article``.

    Losing a fan-out is recoverable and visible in the log; losing the caller's
    transaction is neither.
    """
    resolver = _RESOLVERS.get(audience)
    if resolver is None:
        logger.warning("no resolver for audience %s; delivering to nobody", audience)
        return set()
    try:
        return resolver(ctx, content)
    except Exception:
        logger.exception(
            "could not resolve audience %s for %s; delivering to nobody",
            audience,
            getattr(content, "verb", content),
        )
        return set()


def _apply_exclusions(
    receivers: Set[int], exclusions: tuple, content: object
) -> Set[int]:
    if Exclusion.SUBJECT in exclusions:
        subject_id = _attr(content, "subject_id")
        if subject_id is not None:
            receivers = receivers - {subject_id}
    return receivers


# --------------------------------------------------------------------------
# Activity preconditions.
# --------------------------------------------------------------------------


def _activity_precondition(ctx: RequestContext, c: object) -> bool:
    """Whether this content is eligible for an Activity row *right now*.

    Only comments have one: a comment reaches the timeline solely when it was
    shared there. The flag is persisted on the comment, so it is derived rather
    than passed.
    """
    if isinstance(
        c,
        (
            ev.CommentQuestionInternal,
            ev.CommentAnswerInternal,
            ev.CommentArticleInternal,
            ev.CommentSubmissionInternal,
            ev.ReplyCommentInternal,
        ),
    ):
        comment = _comment_of(ctx, c)
        return bool(comment is not None and comment.shared_to_timeline)
    return True


# --------------------------------------------------------------------------
# Delivery.
# --------------------------------------------------------------------------


def deliver(
    ctx: RequestContext, activity: models.Activity, receiver_ids: Set[int]
) -> None:
    """Write one Feed row per receiver.

    The single place fan-out happens, so that swapping fan-out-on-write for a
    read-time join stays a change to one function.
    """
    assert activity.id is not None
    db = ctx.get_db()
    subject_user_uuid = None
    event = EventInternal.parse_raw(activity.event_json)
    subject_id = _attr(event.content, "subject_id")
    if subject_id is not None:
        subject = crud.user.get(db, id=subject_id)
        if subject is not None:
            subject_user_uuid = subject.uuid
    for receiver_id in receiver_ids:
        existing = (
            db.query(models.Feed)
            .filter_by(receiver_id=receiver_id, activity_id=activity.id)
            .first()
        )
        if existing is None:
            db.add(
                models.Feed(
                    receiver_id=receiver_id,
                    activity_id=activity.id,
                    subject_user_uuid=subject_user_uuid,
                )
            )


def notify_users(
    ctx: RequestContext, event: EventInternal, receiver_ids: Set[int]
) -> None:
    """Write and push a Notification per receiver.

    Public for the one audience :func:`distribute` cannot resolve: the handles
    for ``mentioned_in_comment`` come from the request payload, not the event.
    Everything else should go through :func:`distribute`.
    """
    db = ctx.get_db()
    for receiver_id in sorted(receiver_ids):
        notification = crud.notification.create(
            db,
            obj_in=NotificationCreate(
                receiver_id=receiver_id,
                # Deliberately wall-clock, not event.created_at: this matches
                # what crud.notification.create_with_content has always done,
                # and Notification.created_at is what the unread list sorts by.
                created_at=datetime.datetime.now(tz=datetime.timezone.utc),
                event_json=event.json(),
            ),
        )
        # Same reasoning as _resolve: the row is durable in the caller's
        # transaction and the receiver will see it on their next load. A Redis
        # blip must not undo that, nor the caller's other writes.
        try:
            push_notification(ctx, notif=notification)
        except Exception:
            logger.exception(
                "could not push notification %s to user %s; row still written",
                notification.id,
                receiver_id,
            )


# --------------------------------------------------------------------------
# The seam.
# --------------------------------------------------------------------------


def distribute(
    ctx: RequestContext,
    event: EventInternal,
    *,
    sinks: FrozenSet[Sink] = ALL_SINKS,
) -> Optional[models.Activity]:
    """Route ``event`` to every sink its policy names. Returns the Activity.

    ``sinks`` narrows the destinations. It exists for the two places where one
    verb legitimately reaches different sinks from different callers -- see the
    call sites in ``postprocess.postprocess_comment_update`` and
    ``me.follow_user``. Leave it alone otherwise; the default is the point.
    """
    content = event.content
    policy = POLICY.get(content.verb)
    if policy is None:
        logger.error("no policy for verb %s; event dropped", content.verb)
        return None

    activity: Optional[models.Activity] = None
    if (
        Sink.ACTIVITY in sinks
        and policy.writes_activity
        and _activity_precondition(ctx, content)
    ):
        db = ctx.get_db()
        activity = models.Activity(
            created_at=event.created_at,
            site_id=_site_id_of(ctx, content),
            event_json=event.json(),
        )
        db.add(activity)
        db.flush()

    if Sink.FEED in sinks and activity is not None and policy.feed_audience:
        feed_receivers: Set[int] = set()
        for audience in policy.feed_audience:
            feed_receivers |= _resolve(ctx, audience, content)
        deliver(ctx, activity, feed_receivers)

    if Sink.NOTIFICATION in sinks and policy.notifies:
        notify_receivers: Set[int] = set()
        for audience in policy.notifies:
            notify_receivers |= _resolve(ctx, audience, content)
        notify_receivers = _apply_exclusions(
            notify_receivers, policy.notify_exclusions, content
        )
        notify_users(ctx, event, notify_receivers)

    return activity

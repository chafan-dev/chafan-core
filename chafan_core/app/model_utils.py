import datetime
from typing import List

from chafan_core.app import models


def is_live_answer(answer: models.Answer) -> bool:
    return (
        (not answer.is_deleted)
        and (not answer.is_hidden_by_moderator)
        and answer.is_published
    )


def get_live_answers_of_question(question: models.Question) -> List[models.Answer]:
    return [a for a in question.answers if is_live_answer(a)]


def is_live_article(article: models.Article) -> bool:
    return (not article.is_deleted) and article.is_published


def is_usable_invitation_link(invitation_link: models.InvitationLink) -> bool:
    """Whether `invitation_link` can still bring someone in.

    A link dies when its quota runs out or when it gets too old, whichever
    happens first. This is the same predicate the `valid` field of the
    serialized link reports, so what a caller sees is what redemption enforces.
    """
    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    return invitation_link.expired_at > utc_now and invitation_link.remaining_quota > 0

import datetime
import enum
from enum import Enum
from typing import Callable, List, Literal, Optional, TypeVar, Union

import shortuuid
from fastapi.exceptions import HTTPException
from pytz import utc

ErrorMsg = Union[
    Literal["The site with this id does not exist in the system"],
    Literal["The secondary email already exists."],
    Literal["Inactive user"],
    Literal["Author can't upvote authored question."],
    Literal["Must provide verification code for non-secondary email."],
    Literal["Insufficient coins."],
    Literal["The topic doesn't exists in the system."],
    Literal["The deposit doesn't exist in the system."],
    Literal["No verified email."],
    Literal["Invalid owner UUID"],
    Literal["The article column is not owned by current user."],
    Literal["The application doesn't exists in the system."],
    Literal["Unauthorized."],
    Literal["The submission doesn't exists in the system."],
    Literal["You can't invite yourself."],
    Literal["Incorrect email or password"],
    Literal["The reward doesn't exists in the system."],
    Literal["Invalid site UUID"],
    Literal["The article_column doesn't exists in the system."],
    Literal["User can't follow self."],
    Literal["The user doesn't exist."],
    Literal["Unsupported status."],
    Literal["The reward is already claimed"],
    Literal["The form doesn't exists in the system."],
    Literal["Invalid task type."],
    Literal["Can't hide question with answers."],
    Literal["The site doesn't exist."],
    Literal["Must provide verification code for adding new secondary email."],
    Literal["Invalid input."],
    Literal["Invalid submission UUID."],
    Literal["Request failed."],
    Literal["Upload requires login."],
    Literal["Unauthorized"],
    Literal["The site doesn't exists in the system."],
    Literal["Invalid form response id."],
    Literal["The site with this subdomain already exists in the system."],
    Literal["The topic doesn't exist."],
    Literal["Invalid token"],
    Literal["The reward is not for current user"],
    Literal["The answer doesn't exists in the system."],
    Literal["You have saved an answer before."],
    Literal["Invalid invitation link"],
    Literal["Claimed."],
    Literal["Invalid link"],
    Literal["User can't unfollow self."],
    Literal["Incorrect hCaptcha"],
    Literal["Wrong receiver."],
    Literal["Frondend bug: repeated posting in one writing session."],
    Literal["Insufficient karma."],
    Literal["Only author of submission can do this."],
    Literal["Invalid email."],
    Literal["Current user is not allowed in this site."],
    Literal["The question doesn't exists in the system."],
    Literal["Wrong form."],
    Literal["error_msg,"],
    Literal["User not found"],
    Literal["The channel doesn't exists in the system."],
    Literal["Invalid new moderator UUID"],
    Literal["The reward condition is not met yet"],
    Literal["Invalid request."],
    Literal["Could not validate current user's JWT credentials"],
    Literal["Author can't upvote authored answer."],
    Literal["Applied."],
    Literal["Cyclic parent topic relationship."],
    Literal["The comment doesn't exists in the system."],
    Literal["Missing hCaptcha token"],
    Literal["The user with this username already exists in the system"],
    Literal["Insuffient karma for joining site."],
    Literal["Invalid category topic id."],
    Literal["Author can't upvote authored comment."],
    Literal["The verification code is not present in the system."],
    Literal["The receiver can't post answer for that question."],
    Literal["Duplicated ref_id."],
    Literal["The site with this name already exists in the system."],
    Literal["No such account."],
    Literal["Unauthenticated."],
    Literal["Invalid hostname for link preview."],
    Literal["Could not validate credentials"],
    Literal["Invalid amount."],
    Literal["The site doesn't have moderator."],
    Literal["The submission_suggestion doesn't exists in the system."],
    Literal["The article doesn't exists in the system."],
    Literal["The answer is not authored by current user."],
    Literal["The article column doesn't exist."],
    Literal["Invalid site UUID."],
    Literal["The reward is already refunded"],
    Literal["The user with this email already exists in the system"],
    Literal["The reward is already expired"],
    Literal["Only author of suggestion can do this."],
    Literal["Insuffient coins."],
    Literal["Unknown status."],
    Literal["The message doesn't exists in the system."],
    Literal["User doesn't exist."],
    Literal["You haven't voted yet."],
    Literal["You can't upvote twice."],
    Literal["The site is not moderated by current user."],
    Literal["The user with this email already exists in the system."],
    Literal["Not pending."],
    Literal["Invalid verification code."],
    Literal["The secondary email doesn't exist."],
    Literal["The user with this username does not exist in the system"],
    Literal["The followed_user doesn't exists in the system."],
    Literal["The comment has too many or too few parent ids."],
    Literal["Author can't upvote authored submission."],
    Literal["The receiver doesn't exists in the system."],
    Literal["Can't change accepted suggestion."],
    Literal["Author can't upvote authored article."],
    Literal["The user with this email does not exist in the system."],
    Literal["The circle doesn't exists in the system."],
    Literal["The profile exists."],
    Literal["The user doesn't have enough privileges"],
    Literal["Invalid user UUID."],
    Literal["The username can't be empty"],
    Literal["The payee doesn't exist in the system."],
    Literal["The user doesn't exists in the system."],
    Literal["The comment is not authored by the current user."],
    Literal["This primary email is already used in the website."],
    Literal["The form doesn't belong to current user."],
    Literal["Open user registration is forbidden on this server"],
    Literal["Not for a specific site"],
    Literal["Question has at least one answers."],
    Literal["Invalid password."],
    Literal["Delete answer failed."],
    Literal["The feedback doesn't exist."],
    Literal["The feedback has no screenshot."],
    Literal["Unavailable link preview."],
    Literal["Answer has no draft."],
    Literal["Only author of answer can do this."],
    Literal["The answer_suggest_edit doesn't exists in the system."],
    Literal["The answer has draft with potential conflict."],
    Literal["The report has too many or too few object ids."],
]


def HTTPException_(status_code: int, detail: ErrorMsg) -> HTTPException:
    return HTTPException(status_code=status_code, detail=detail)


class EntityType(str, Enum):
    sites = "sites"
    users = "users"


def get_utc_now() -> datetime.datetime:
    return datetime.datetime.now(tz=datetime.timezone.utc)


T = TypeVar("T")
S = TypeVar("S")


def map_(v: Optional[T], f: Callable[[T], S]) -> Optional[S]:
    if v is not None:
        return f(v)
    return None


def filter_not_none(vs: List[Optional[T]]) -> List[T]:
    return [v for v in vs if v is not None]


def unwrap(v: Optional[T]) -> T:
    assert v is not None
    return v


def dedup(vs: List[T]) -> List[T]:
    return list(set(vs))


UUID_LENGTH = 20


def get_uuid() -> str:
    return shortuuid.ShortUUID().random(length=UUID_LENGTH)


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    FINISHED = "finished"
    FAILED = "failed"


# If in public site: World visible > registered user visible > [my friends visible -- in future]
# If in private site: site members visible > [my friends visible -- in future]
class ContentVisibility(str, enum.Enum):
    ANYONE = "anyone"
    REGISTERED = "registered"
    # TODO: FRIENDS


class ReportReason(str, enum.Enum):
    # CoC 2, 4, 8
    SPAM = "SPAM"
    # CoC 3
    OFF_TOPIC = "OFF_TOPIC"
    # CoC 5, 6, 10
    RUDE_OR_ABUSIVE = "RUDE_OR_ABUSIVE"
    # CoC 1
    NEEDS_IMPROVEMENT = "NEEDS_IMPROVEMENT"
    # CoC 7, 9
    RIGHT_INFRINGEMENT = "RIGHT_INFRINGEMENT"
    DUPLICATE = "DUPLICATE"
    NEED_MODERATOR_INTERVENTION = "NEED_MODERATOR_INTERVENTION"


def parse_yyyy_mm_dd_utc(s: str) -> datetime.datetime:
    return datetime.datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=utc)

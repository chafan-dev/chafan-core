import datetime
import enum
import re
from typing import Any, Mapping, NamedTuple, Optional, Tuple

import arrow  # type: ignore
import redis
import sentry_sdk
from fastapi import Header, Request
from html2text import HTML2Text
from jinja2 import Template
from jose import jwt
from pymongo import MongoClient  # type: ignore
from pymongo.database import Database as MongoDB  # type: ignore

from chafan_core.app import schemas
from chafan_core.app.config import settings
from chafan_core.app.schemas.event import Event
from chafan_core.utils.base import HTTPException_, unwrap
from chafan_core.utils.validators import CaseInsensitiveEmailStr


class OperationType(enum.Enum):
    ReadSite = 0
    WriteSiteQuestion = 1
    WriteSiteComment = 2
    WriteSiteAnswer = 3
    AddSiteMember = 4
    WriteSiteSubmission = 5


_redis_pool: Optional[redis.Redis] = None

# NOTE: try sharing the redis connections
def get_redis_cli() -> redis.Redis:
    from chafan_core.app.config import settings

    global _redis_pool
    if _redis_pool is None:
        _redis_pool = redis.from_url(
            settings.REDIS_URL, decode_responses=True, max_connections=60
        )
    return _redis_pool


_mongo_pool: Optional[MongoClient] = None


def get_mongo_db() -> MongoDB:
    from chafan_core.app.config import settings

    global _mongo_pool
    if not _mongo_pool:
        _mongo_pool = MongoClient(settings.MONGO_CONNECTION)
    return _mongo_pool.get_database("chafan_" + settings.ENV)


MAX_FILE_SIZE = 10_000_000


async def valid_content_length(
    content_length: int = Header(..., lt=MAX_FILE_SIZE)
) -> int:
    return content_length


def is_dev() -> bool:
    from chafan_core.app.config import settings

    return settings.ENV == "dev"


def enable_rate_limit() -> bool:
    from chafan_core.app.config import settings

    return not is_dev() or settings.FORCE_RATE_LIMIT


def run_dramatiq_task(task: Any, *arg: Any, **kwargs: Any) -> None:
    if is_dev():
        task(*arg, **kwargs)
    else:
        task.send(*arg, **kwargs)


def from_now(utc: datetime.datetime, locale: str) -> str:
    return arrow.get(utc).humanize(locale=locale)


def generate_password_reset_token(email: CaseInsensitiveEmailStr) -> str:
    delta = datetime.timedelta(hours=settings.EMAIL_RESET_TOKEN_EXPIRE_HOURS)
    now = datetime.datetime.utcnow()
    expires = now + delta
    encoded_jwt = jwt.encode(
        {"exp": expires, "nbf": now, "email": str(email)},
        unwrap(settings.SECRET_KEY),
        algorithm="HS256",
    )
    return encoded_jwt


def check_token_validity_impl(token: str) -> bool:
    try:
        jwt.decode(token, unwrap(settings.SECRET_KEY), algorithms=["HS256"])
        return True
    except Exception:
        return False


def verify_password_reset_token(token: str) -> Optional[str]:
    try:
        decoded_token = jwt.decode(
            token, unwrap(settings.SECRET_KEY), algorithms=["HS256"]
        )
        return decoded_token["email"]
    except Exception:
        return None


def html2plaintext(t: str) -> str:
    h = HTML2Text()
    h.ignore_links = True
    return h.handle(t).strip()


EVENT_TEMPLATES: Mapping[str, Tuple[str, str]] = {
    "create_question": ("{{who}}创建了问题", "「{{question}}」"),
    "create_site": ("{{who}}创建了圈子", "「{{site}}」"),
    "create_site_need_approval": ("{{who}}申请创建圈子", "（{{channel}}）"),
    "create_submission": ("{{who}}创建了分享", "「{{submission}}」"),
    "create_submission_suggestion": (
        "{{who}}添加了对分享的建议编辑",
        "「{{submission_suggestion}}」",
    ),
    "accept_submission_suggestion": (
        "{{who}}采纳了对分享的建议编辑",
        "「{{submission_suggestion}}」",
    ),
    "create_answer_suggest_edit": (
        "{{who}}添加了对问题回答的建议编辑",
        "「{{answer_suggest_edit}}」",
    ),
    "accept_answer_suggest_edit": (
        "{{who}}采纳了对问题回答的建议编辑",
        "「{{answer_suggest_edit}}」",
    ),
    "create_article": ("{{who}}发表了文章", "「{{article}}」"),
    "follow_article_column": ("{{who}}关注了专栏", "「{{article_column}}」"),
    "upvote_question": ("{{who}}赞了问题", "「{{question}}」"),
    "edit_question": ("{{who}}修改了问题", "「{{question}}」"),
    "upvote_submission": ("{{who}}赞了分享", "「{{submission}}」"),
    "invited_user_activated": ("你邀请的用户已激活账户", "：{{invited_email}}"),
    "upvote_article": ("{{who}}赞了文章", "「{{article}}」"),
    "answer_question": ("{{who}}回答了你的问题", "「{{question}}」：「{{answer}}」"),
    "answer_update": ("{{who}}更新了回答", "「{{question}}」：「{{answer}}」"),
    "comment_question": ("{{who}}评论了你的问题", "「{{question}}」：「{{comment}}」"),
    "comment_submission": ("{{who}}评论了你的分享", "「{{submission}}」：「{{comment}}」"),
    "reply_comment": ("{{who}}回复了你的评论", "「{{parent_comment}}」：「{{reply}}」"),
    "invite_answer": ("{{who}}邀请你回答问题", "「{{question}}」"),
    "invite_join_site": ("{{who}}邀请你加入圈子", "「{{site}}」"),
    "apply_join_site": ("{{who}}申请加入圈子", "「{{site}}」"),
    "comment_answer": ("{{who}}评论了你对问题的回答", "「{{question}}」：「{{comment}}」"),
    "comment_article": ("{{who}}评论了你的文章", "「{{article}}」：「{{comment}}」"),
    "upvote_answer": ("{{who}}赞了你对问题的回答", "「{{question}}」：「{{answer}}」"),
    "follow_user": ("{{who}}关注了你", ""),
    "system_broadcast": ("📢 系统广播", "：『{{message}}』"),
    "site_broadcast": ("📢 「'{{site}}'」广播", "：「{{submission}}」"),
    "create_message": ("{{who}} 私信了你", ""),
    "system_send_invitation": ("系统已发送邀请邮件", "给 {{invited_email}}"),
    "create_answer_question_reward": (
        "{{who}}创建了{{reward_coin_amount}}个硬币的奖励",
        "来邀请你回答「{{question}}」",
    ),
    "claim_answer_question_reward": (
        "{{who}} 兑换了回答问题的{{reward_coin_amount}}个硬币的奖励",
        "",
    ),
    "invite_new_user": (
        "你邀请的用户已激活账户 {{invited_email}}",
        "{% if payment_amount %}，你已经收到 {{payment_amount}} 硬币奖励{% endif %}",
    ),
    "mentioned_in_comment": ("{{who}} 在评论中提到了你", "：「{{comment}}」"),
}


class RenderedNotif(NamedTuple):
    headline: str
    full: str


def render_notif_content(notif: schemas.Notification) -> Optional[RenderedNotif]:
    event = notif.event
    if event is None:
        return None
    return render_event(event)


def render_event(event: Event) -> RenderedNotif:
    part1, part2 = EVENT_TEMPLATES[event.content.verb]
    return RenderedNotif(
        headline=html2plaintext(Template(part1).render(**event.content._string_args())),
        full=Template(part1 + part2).render(**event.content._string_args()),
    )


def is_email(email: str) -> bool:
    return re.fullmatch(r"[^@]+@[^@]+\.[^@]+", email) is not None


def client_ip(request: Request) -> str:
    if "x-forwarded-for" in request.headers:
        r = request.headers["x-forwarded-for"].split(", ")[0]
        return r
    if request.client:
        return request.client.host or "127.0.0.1"
    return "127.0.0.1"


def report_msg(msg: str) -> None:
    if not is_dev():
        sentry_sdk.capture_message(msg)
    else:
        raise Exception(msg)


def check_email(email: str) -> None:
    if not is_email(email):
        raise HTTPException_(
            status_code=404,
            detail="Invalid email.",
        )

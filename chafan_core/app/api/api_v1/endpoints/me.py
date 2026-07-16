from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Query

from chafan_core.app import schemas
from chafan_core.app.api import deps
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.schemas.user import (
    UserUpdateLoginPhoneNumber,
    UserUpdateMe,
    UserUpdatePrimaryEmail,
    UserUpdateSecondaryEmails,
)
from chafan_core.app.services import me as me_service
from chafan_core.utils.constants import MAX_MY_SUBSCRIBED_ITEMS_PAGINATION_LIMIT

router = APIRouter()


############################## User self-management ##############################


# NOTE: don't change route to "/"
@router.get("", response_model=schemas.User)
def read_user_me(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
) -> Any:
    """
    Get current user.
    """
    return me_service.get_me(ctx)


# NOTE: don't change route to "/"
@router.put("", response_model=schemas.User)
def update_user_me(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    user_in: UserUpdateMe,
) -> Any:
    """
    Update own user.
    """
    return me_service.update_me(ctx, user_in=user_in)


@router.put("/login", response_model=schemas.User)
def update_user_login_email(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    user_in: UserUpdatePrimaryEmail,
) -> Any:
    return me_service.update_login_email(ctx, user_in=user_in)


@router.put("/secondary-emails", response_model=schemas.User)
def update_user_secondary_emails(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    user_in: UserUpdateSecondaryEmails,
) -> Any:
    return me_service.update_secondary_emails(ctx, user_in=user_in)


@router.put("/phone-number", response_model=schemas.User)
def update_user_phone_number(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    user_in: UserUpdateLoginPhoneNumber,
) -> Any:
    return me_service.update_phone_number(ctx, user_in=user_in)


######################### User Follows User #########################


@router.get("/follows/{uuid}", response_model=schemas.UserFollows)
def get_user_follows(
    *,
    ctx: RequestContext = Depends(deps.get_request_context),
    uuid: str,
) -> Any:
    """
    Get a user's follows info.
    """
    return me_service.get_follows(ctx, uuid=uuid)


@router.post("/follows/{uuid}", response_model=schemas.UserFollows)
def follow_user(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    uuid: str,
) -> Any:
    """
    Follow a user.
    """
    return me_service.follow_user(ctx, uuid=uuid)


@router.delete("/follows/{uuid}", response_model=schemas.UserFollows)
def cancel_follow_user(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    uuid: str,
) -> Any:
    """
    Cancel follow of user.
    """
    return me_service.cancel_follow_user(ctx, uuid=uuid)


@router.get("/channels/", response_model=List[schemas.Channel])
def get_user_channels(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
) -> Any:
    """
    Get a user's all channels.
    """
    return me_service.list_channels(ctx)


@router.get("/article-columns/", response_model=List[schemas.ArticleColumn])
def get_user_article_columns(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
) -> Any:
    """
    Get a user's all article_columns.
    """
    return me_service.list_my_article_columns(ctx)


######################### User Subscribes Question #########################


@router.get(
    "/question-subscriptions/{uuid}", response_model=schemas.UserQuestionSubscription
)
def get_user_question_subscription(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    uuid: str,
) -> Any:
    """
    Get current user's info about a question's subscription.
    """
    return me_service.get_question_subscription(ctx, uuid=uuid)


@router.get(
    "/question-subscriptions/", response_model=List[Optional[schemas.QuestionPreview]]
)
def get_user_question_subscriptions(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(
        default=MAX_MY_SUBSCRIBED_ITEMS_PAGINATION_LIMIT,
        le=MAX_MY_SUBSCRIBED_ITEMS_PAGINATION_LIMIT,
        gt=0,
    ),
) -> Any:
    """
    Get current user's subscribed questions.
    """
    return me_service.list_subscribed_questions(ctx, skip=skip, limit=limit)


@router.post(
    "/question-subscriptions/{uuid}", response_model=schemas.UserQuestionSubscription
)
def subscribe_question(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    uuid: str,
) -> Any:
    """
    Subscribe a question.
    """
    return me_service.subscribe_question(ctx, uuid=uuid)


@router.delete(
    "/question-subscriptions/{uuid}", response_model=schemas.UserQuestionSubscription
)
def unsubscribe_question(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    uuid: str,
) -> Any:
    """
    Unsubscribe a question.
    """
    return me_service.unsubscribe_question(ctx, uuid=uuid)


######################### User Subscribes Submission #########################


@router.get(
    "/submission-subscriptions/{uuid}",
    response_model=schemas.UserSubmissionSubscription,
)
def get_user_submission_subscription(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    uuid: str,
) -> Any:
    """
    Get current user's info about a submission's subscription.
    """
    return me_service.get_submission_subscription(ctx, uuid=uuid)


@router.get(
    "/submission-subscriptions/", response_model=List[Optional[schemas.Submission]]
)
def get_user_submission_subscriptions(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(
        default=MAX_MY_SUBSCRIBED_ITEMS_PAGINATION_LIMIT,
        le=MAX_MY_SUBSCRIBED_ITEMS_PAGINATION_LIMIT,
        gt=0,
    ),
) -> Any:
    """
    Get current user's subscribed submissions.
    """
    return me_service.list_subscribed_submissions(ctx, skip=skip, limit=limit)


@router.post(
    "/submission-subscriptions/{uuid}",
    response_model=schemas.UserSubmissionSubscription,
)
def subscribe_submission(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    uuid: str,
) -> Any:
    """
    Subscribe a submission.
    """
    return me_service.subscribe_submission(ctx, uuid=uuid)


@router.delete(
    "/submission-subscriptions/{uuid}",
    response_model=schemas.UserSubmissionSubscription,
)
def unsubscribe_submission(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    uuid: str,
) -> Any:
    """
    Unsubscribe a submission.
    """
    return me_service.unsubscribe_submission(ctx, uuid=uuid)


######################### User bookmarks answer #########################


@router.get("/answer-bookmarks/", response_model=List[Optional[schemas.AnswerPreview]])
def get_user_answer_bookmarks(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(
        default=MAX_MY_SUBSCRIBED_ITEMS_PAGINATION_LIMIT,
        le=MAX_MY_SUBSCRIBED_ITEMS_PAGINATION_LIMIT,
        gt=0,
    ),
) -> Any:
    return me_service.list_bookmarked_answers(ctx, skip=skip, limit=limit)


@router.post("/answer-bookmarks/{uuid}", response_model=schemas.UserAnswerBookmark)
def bookmark_answer(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    uuid: str,
) -> Any:
    return me_service.bookmark_answer(ctx, uuid=uuid)


@router.delete("/answer-bookmarks/{uuid}", response_model=schemas.UserAnswerBookmark)
def unbookmark_answer(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    uuid: str,
) -> Any:
    return me_service.unbookmark_answer(ctx, uuid=uuid)


@router.get(
    "/article-bookmarks/", response_model=List[Optional[schemas.ArticlePreview]]
)
def get_user_article_bookmarks(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(
        default=MAX_MY_SUBSCRIBED_ITEMS_PAGINATION_LIMIT,
        le=MAX_MY_SUBSCRIBED_ITEMS_PAGINATION_LIMIT,
        gt=0,
    ),
) -> Any:
    return me_service.list_bookmarked_articles(ctx, skip=skip, limit=limit)


@router.post("/article-bookmarks/{uuid}", response_model=schemas.UserArticleBookmark)
def bookmark_article(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    uuid: str,
) -> Any:
    return me_service.bookmark_article(ctx, uuid=uuid)


@router.delete("/article-bookmarks/{uuid}", response_model=schemas.UserArticleBookmark)
def unbookmark_article(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    uuid: str,
) -> Any:
    return me_service.unbookmark_article(ctx, uuid=uuid)


######################### User Subscribes Topic #########################


@router.get("/topic-subscriptions/{uuid}", response_model=schemas.UserTopicSubscription)
def get_user_topic_subscription(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    uuid: str,
) -> Any:
    """
    Get current user's info about a topic's subscription.
    """
    return me_service.get_topic_subscription(ctx, uuid=uuid)


@router.post(
    "/topic-subscriptions/{uuid}", response_model=schemas.UserTopicSubscription
)
def subscribe_topic(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    uuid: str,
) -> Any:
    """
    Subscribe a topic.
    """
    return me_service.subscribe_topic(ctx, uuid=uuid)


@router.delete(
    "/topic-subscriptions/{uuid}", response_model=schemas.UserTopicSubscription
)
def unsubscribe_topic(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    uuid: str,
) -> Any:
    """
    Unsubscribe a topic.
    """
    return me_service.unsubscribe_topic(ctx, uuid=uuid)


######################### User Subscribes Article Column #########################


@router.get(
    "/article-column-subscriptions/{uuid}",
    response_model=schemas.UserArticleColumnSubscription,
)
def get_user_article_column_subscription(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    uuid: str,
) -> Any:
    """
    Get current user's info about a article_column's subscription.
    """
    return me_service.get_article_column_subscription(ctx, uuid=uuid)


@router.get(
    "/article-column-subscriptions/", response_model=List[schemas.ArticleColumn]
)
def get_user_article_column_subscriptions(
    *,
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
) -> Any:
    """
    Get current user's all subscribed article columns.
    """
    return me_service.list_subscribed_article_columns(ctx)


@router.post(
    "/article-column-subscriptions/{uuid}",
    response_model=schemas.UserArticleColumnSubscription,
)
def subscribe_article_column(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    uuid: str,
) -> Any:
    """
    Subscribe a article_column.
    """
    return me_service.subscribe_article_column(ctx, uuid=uuid)


@router.delete(
    "/article-column-subscriptions/{uuid}",
    response_model=schemas.UserArticleColumnSubscription,
)
def unsubscribe_article_column(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
    *,
    uuid: str,
) -> Any:
    """
    Unsubscribe a article_column.
    """
    return me_service.get_article_column_subscription_after_unsubscribe(
        ctx, uuid=uuid
    )


@router.get("/site-profiles/", response_model=List[schemas.Profile])
def get_site_profiles(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
) -> Any:
    return me_service.list_site_profiles(ctx)


@router.get(
    "/moderated-sites/", response_model=List[schemas.Site], include_in_schema=False
)
def get_moderated_sites(
    ctx: RequestContext = Depends(deps.get_request_context_logged_in),
) -> Any:
    return me_service.list_moderated_sites(ctx)

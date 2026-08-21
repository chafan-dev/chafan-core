from fastapi import APIRouter

from chafan_core.app.api.api_v1.endpoints import (
    activities,
    answer_suggest_edits,
    answers,
    applications,
    article_columns,
    articles,
    audit_logs,
    bot,
    channels,
    coin_deposits,
    coin_payments,
    comments,
    discovery,
    drafts,
    feedbacks,
    form_responses,
    forms,
    invitation_links,
    login,
    me,
    messages,
    notifications,
    people,
    profiles,
    questions,
    reports,
    rewards,
    search,
    sitemaps,
    sites,
    submission_suggestions,
    submissions,
    topics,
    upload,
    users,
    webhooks,
    ws,
    rss,
    admin_tools,
)

api_router = APIRouter()
api_router.include_router(login.router, tags=["login"])
api_router.include_router(drafts.router, prefix="/drafts", tags=["drafts"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(people.router, prefix="/people", tags=["people"])
api_router.include_router(forms.router, prefix="/forms", tags=["forms"])
api_router.include_router(
    form_responses.router, prefix="/form-responses", tags=["form-responses"]
)
api_router.include_router(sites.router, prefix="/sites", tags=["sites"])
api_router.include_router(profiles.router, prefix="/profiles", tags=["profiles"])
api_router.include_router(questions.router, prefix="/questions", tags=["questions"])
api_router.include_router(answers.router, prefix="/answers", tags=["answers"])
api_router.include_router(articles.router, prefix="/articles", tags=["articles"])
api_router.include_router(
    invitation_links.router, prefix="/invitation-links", tags=["invitation-links"]
)
api_router.include_router(
    article_columns.router, prefix="/article-columns", tags=["article-columns"]
)
api_router.include_router(comments.router, prefix="/comments", tags=["comments"])
api_router.include_router(activities.router, prefix="/activities", tags=["activities"])
api_router.include_router(me.router, prefix="/me", tags=["me"])
api_router.include_router(topics.router, prefix="/topics", tags=["topics"])
api_router.include_router(channels.router, prefix="/channels", tags=["channels"])
api_router.include_router(messages.router, prefix="/messages", tags=["messages"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(discovery.router, prefix="/discovery", tags=["discovery"])
api_router.include_router(rss.router, prefix="/rss", tags=["rss"])
api_router.include_router(upload.router, prefix="/upload", tags=["upload"])
api_router.include_router(ws.router, prefix="/ws", tags=["ws"])
api_router.include_router(
    submissions.router, prefix="/submissions", tags=["submissions"]
)
api_router.include_router(
    submission_suggestions.router,
    prefix="/submission-suggestions",
    tags=["submission_suggestions"],
)
api_router.include_router(
    answer_suggest_edits.router,
    prefix="/answer-suggest-edits",
    tags=["answer_suggest_edits"],
)
api_router.include_router(
    applications.router, prefix="/applications", tags=["applications"]
)
api_router.include_router(
    notifications.router, prefix="/notifications", tags=["notifications"]
)
api_router.include_router(
    coin_deposits.router, prefix="/coin-deposits", tags=["coin_deposits"]
)
api_router.include_router(
    coin_payments.router, prefix="/coin-payments", tags=["coin_payments"]
)
api_router.include_router(audit_logs.router, prefix="/audit-logs", tags=["audit_logs"])
api_router.include_router(admin_tools.router, prefix="/admin_tools", tags=["admin_tools"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(feedbacks.router, prefix="/feedbacks", tags=["feedbacks"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(rewards.router, prefix="/rewards", tags=["rewards"])
api_router.include_router(sitemaps.router, prefix="/sitemaps", tags=["sitemaps"])
api_router.include_router(bot.router, prefix="/bot", tags=["bot"])

from typing import List

import jieba.analyse  # type: ignore
from pydantic.tools import parse_obj_as
from sqlalchemy.orm.session import Session

from chafan_core.app import crud, models
from chafan_core.app.schemas.user import (
    UserEducationExperienceInternal,
    UserWorkExperienceInternal,
)
from chafan_core.app.task_utils import execute_with_db
from chafan_core.db.session import SessionLocal
from chafan_core.utils.base import dedup, unwrap


def get_keywords(text: str, topK: int = 10) -> List[str]:
    return jieba.analyse.extract_tags(text, topK=topK)


def update_question_keywords(question: models.Question) -> None:
    keywords = get_keywords(question.title, topK=3)
    if question.description_text:
        keywords.extend(get_keywords(question.description_text, topK=3))
    if question.topics:
        keywords.extend([topic.name for topic in question.topics])
    question.keywords = dedup(keywords)


def update_submission_keywords(submission: models.Submission) -> None:
    keywords = get_keywords(submission.title, topK=3)
    if submission.description_text:
        keywords.extend(get_keywords(submission.description_text, topK=3))
    if submission.topics:
        keywords.extend([topic.name for topic in submission.topics])
    submission.keywords = dedup(keywords)


def update_answer_keywords(answer: models.Answer) -> None:
    if answer.body_prerendered_text:
        answer.keywords = get_keywords(answer.body_prerendered_text)


def update_article_keywords(article: models.Article) -> None:
    keywords = get_keywords(article.title, topK=3)
    if article.body_text:
        keywords.extend(get_keywords(article.body_text))
    if article.topics:
        keywords.extend([topic.name for topic in article.topics])
    article.keywords = dedup(keywords)


def update_article_column_keywords(article_column: models.ArticleColumn) -> None:
    keywords = [article_column.name]
    if article_column.description:
        keywords.extend(get_keywords(article_column.description, topK=5))
    for article in article_column.articles:
        if article.keywords:
            keywords.extend(article.keywords)
    article_column.keywords = dedup(keywords)


def update_site_keywords(site: models.Site) -> None:
    keywords: List[str] = [site.name]
    if site.description:
        keywords.extend(get_keywords(site.description, topK=5))
    if site.topics:
        keywords.extend([topic.name for topic in site.topics])
    for question in site.questions:
        if question.keywords:
            keywords.extend(question.keywords)
    for submission in site.submissions:
        if submission.keywords:
            keywords.extend(submission.keywords)
    site.keywords = dedup(keywords)


def update_user_keywords(db: Session, user: models.User) -> None:
    keywords: List[str] = []
    for t in list(user.subscribed_topics) + list(user.residency_topics):
        keywords.append(t.name)
    keyword_clusters = [
        user.subscribed_article_columns,
        user.bookmarked_articles,
        user.subscribed_questions,
        user.subscribed_submissions,
        user.bookmarked_answers,
        user.questions,
        user.submissions,
        user.answers,
        user.articles,
        user.article_columns,
    ]
    for cluster in keyword_clusters:
        for entity in cluster:
            if entity.keywords:
                keywords.extend(entity.keywords)
    if user.profession_topics:
        keywords.extend([t.name for t in user.profession_topics])
    if user.work_experiences:
        for work_exp in parse_obj_as(
            List[UserWorkExperienceInternal], user.work_experiences
        ):
            keywords.append(
                unwrap(
                    crud.topic.get_by_uuid(db, uuid=work_exp.company_topic_uuid)
                ).name
            )
            keywords.append(
                unwrap(
                    crud.topic.get_by_uuid(db, uuid=work_exp.position_topic_uuid)
                ).name
            )
    if user.education_experiences:
        for edu_exp in parse_obj_as(
            List[UserEducationExperienceInternal], user.education_experiences
        ):
            keywords.append(edu_exp.level_name)
            keywords.append(
                unwrap(crud.topic.get_by_uuid(db, uuid=edu_exp.school_topic_uuid)).name
            )
    if user.personal_introduction:
        keywords.extend(get_keywords(user.personal_introduction, topK=5))
    if user.about:
        keywords.extend(get_keywords(user.about, topK=2))
    for profile in user.profiles:
        if profile.site.keywords:
            keywords.extend(profile.site.keywords)
    user.keywords = dedup(keywords)


def fill_missing_keywords_task() -> None:
    def runnable(db: Session) -> None:
        print("Updating answers keywords")
        for answer in crud.answer.get_all_published(db):
            update_answer_keywords(answer)

        print("Updating questions keywords")
        for question in crud.question.get_all_valid(db):
            update_question_keywords(question)

        print("Updating submissions keywords")
        for submission in crud.submission.get_all_valid(db):
            update_submission_keywords(submission)

        print("Updating article keywords")
        for article in crud.article.get_all_published(db):
            update_article_keywords(article)

        print("Updating article_column keywords")
        for article_column in crud.article_column.get_all(db):
            update_article_column_keywords(article_column)

        print("Updating site keywords")
        for site in crud.site.get_all(db):
            update_site_keywords(site)

        print("Updating user keywords")
        for user in crud.user.get_all_active_users(db):
            update_user_keywords(db, user)

    execute_with_db(SessionLocal(), runnable)

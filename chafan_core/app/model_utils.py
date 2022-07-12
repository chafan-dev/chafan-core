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

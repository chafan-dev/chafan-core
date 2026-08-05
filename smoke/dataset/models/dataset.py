"""Core data structures for the smoke dataset build.

The Dataset dataclass holds the ids produced by build() so callers
(scenarios, migration verify) can find their fixtures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

from chafan_core.app import models


@dataclass
class Dataset:
    """What a build produced, for callers that need the ids.

    Keyed by the same string keys used in user_factory.USERS,
    site_factory.COLUMNS, content_factory.QUESTIONS/ANSWERS/ARTICLES.
    """

    users: Dict[str, models.User]
    site: models.Site
    columns: Dict[str, models.ArticleColumn]
    questions: Dict[str, models.Question]
    answers: Dict[str, models.Answer]
    articles: Dict[str, models.Article]

    # Set by build(deep=True): account_b answering the known question, plus
    # the Activity/Feed/Notification rows distributed from that event.
    deep_answer: Optional[models.Answer] = field(default=None)

    # Convenience aliases for the two original anchor accounts and their
    # single "known" fixtures -- callers like smoke/seed.py only need one
    # stable question/column/account pair to hand the e2e scenarios.
    @property
    def account_a(self) -> models.User:
        return self.users["account_a"]

    @property
    def account_b(self) -> models.User:
        return self.users["account_b"]

    @property
    def column(self) -> models.ArticleColumn:
        return self.columns["column_a"]

    @property
    def question(self) -> models.Question:
        return self.questions["question_a"]

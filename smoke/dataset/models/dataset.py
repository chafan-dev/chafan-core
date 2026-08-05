"""Core data structures for the smoke dataset build.

The Dataset dataclass holds the ids produced by build() so callers
(scenarios, migration verify) can find their fixtures.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from chafan_core.app import models


@dataclass
class Dataset:
    """What a build produced, for callers that need the ids."""

    # Original anchors
    account_a: models.User
    account_b: models.User

    # Extended cast
    site: models.Site
    column_a: models.ArticleColumn
    column_b: models.ArticleColumn
    column_c: models.ArticleColumn
    question_a: models.Question
    question_b: models.Question
    question_c: models.Question
    question_d: models.Question
    question_e: models.Question
    question_f: models.Question
    answer_a: Optional[models.Answer] = None
    answer_b: Optional[models.Answer] = None
    answer_c: Optional[models.Answer] = None
    answer_d: Optional[models.Answer] = None
    article_a: Optional[models.Article] = None
    article_b: Optional[models.Article] = None
    article_c: Optional[models.Article] = None
    article_d: Optional[models.Article] = None

from typing import Optional

from sqlalchemy.orm import Session

from chafan_core.app import crud, models
from chafan_core.app.common import OperationType
from chafan_core.app.config import settings
from chafan_core.utils.base import ContentVisibility


import logging
logger = logging.getLogger(__name__)

# TODO everything about user permission, including if they can create a site (KARMA), invite a user, write an answer, etc, should be moved into this file. 2025-07-08

# Coin payment and karma update should go to this file


def new_submission_suggestion(submission_suggestion):
    pass

def new_question(question):
    pass

def new_submission(submission):
    pass

def accept_submission_suggestion(submission_suggestion):
    pass

def new_answer_suggest(answer_suggest):
    pass

def accept_answer_suggest(answer_suggest_edit):
    pass

def new_article(article):
    pass

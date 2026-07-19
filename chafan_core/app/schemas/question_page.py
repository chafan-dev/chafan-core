from typing import List, Optional

from pydantic import BaseModel

from chafan_core.app.schemas.answer import Answer, AnswerPreview
from chafan_core.app.schemas.question import Question
from chafan_core.app.schemas.user import UserQuestionSubscription


class QuestionPageFlags(BaseModel):
    editable: bool = False
    answer_writable: bool = False
    comment_writable: bool = False
    hideable: bool = False
    is_mod: bool = False


class QuestionPage(BaseModel):
    question: Question
    full_answers: List[Answer]
    answer_previews: List[AnswerPreview]
    question_subscription: Optional[UserQuestionSubscription]
    flags: QuestionPageFlags

from typing import List, Optional, Union

from pydantic import BaseModel

from chafan_core.app.schemas.answer import (
    Answer,
    AnswerForVisitor,
    AnswerPreview,
    AnswerPreviewForVisitor,
)
from chafan_core.app.schemas.question import Question, QuestionForVisitor
from chafan_core.app.schemas.user import UserQuestionSubscription


class QuestionPageFlags(BaseModel):
    editable: bool = False
    answer_writable: bool = False
    comment_writable: bool = False
    hideable: bool = False
    is_mod: bool = False


class QuestionPage(BaseModel):
    question: Union[Question, QuestionForVisitor]
    full_answers: List[Union[Answer, AnswerForVisitor]]
    answer_previews: List[Union[AnswerPreview, AnswerPreviewForVisitor]]
    question_subscription: Optional[UserQuestionSubscription]
    flags: QuestionPageFlags

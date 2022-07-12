from chafan_core.app.crud.base import CRUDBase
from chafan_core.app.models.feedback import Feedback
from chafan_core.app.schemas.feedback import FeedbackCreate, FeedbackUpdate


class CRUDFeedback(CRUDBase[Feedback, FeedbackCreate, FeedbackUpdate]):
    pass


feedback = CRUDFeedback(Feedback)

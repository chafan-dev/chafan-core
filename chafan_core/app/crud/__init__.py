# flake8: noqa

# Each domain is a plain module of functions; the short aliases below keep the
# historical `crud.<domain>.<fn>(db, ...)` call-site surface unchanged.
from . import crud_application as application
from . import crud_article_column as article_column
from . import crud_coin_deposit as coin_deposit
from . import crud_coin_payment as coin_payment
from . import crud_feedback as feedback
from . import crud_form as form
from . import crud_form_response as form_response
from . import crud_invitation as invitation
from . import crud_invitation_link as invitation_link
from . import crud_webhook as webhook
from .crud_activity import activity
from .crud_answer import answer
from .crud_answer_suggest_edit import answer_suggest_edit
from .crud_article import article
from .crud_audit_log import audit_log
from .crud_channel import channel
from .crud_comment import comment
from .crud_message import message
from .crud_notification import notification
from .crud_profile import profile
from .crud_question import question
from .crud_report import report
from .crud_reward import reward
from .crud_site import site
from .crud_submission import submission
from .crud_submission_suggestion import submission_suggestion
from .crud_topic import topic
from .crud_user import user

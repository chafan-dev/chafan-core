# flake8: noqa

# Each domain is a plain module of functions; the short aliases below keep the
# historical `crud.<domain>.<fn>(db, ...)` call-site surface unchanged.
from . import crud_activity as activity
from . import crud_answer as answer
from . import crud_answer_suggest_edit as answer_suggest_edit
from . import crud_application as application
from . import crud_article as article
from . import crud_article_column as article_column
from . import crud_audit_log as audit_log
from . import crud_channel as channel
from . import crud_coin_deposit as coin_deposit
from . import crud_comment as comment
from . import crud_coin_payment as coin_payment
from . import crud_feedback as feedback
from . import crud_form as form
from . import crud_form_response as form_response
from . import crud_invitation as invitation
from . import crud_invitation_link as invitation_link
from . import crud_message as message
from . import crud_notification as notification
from . import crud_profile as profile
from . import crud_report as report
from . import crud_reward as reward
from . import crud_submission_suggestion as submission_suggestion
from . import crud_topic as topic
from . import crud_webhook as webhook
from .crud_question import question
from .crud_site import site
from .crud_submission import submission
from .crud_user import user

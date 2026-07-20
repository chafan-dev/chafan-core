"""Back-compat re-exports for background work.

Prefer importing from services.postprocess / services.viewcounts / services.search.
"""

from chafan_core.app.services.postprocess import (  # noqa: F401
    get_comment_event,
    notify_mentioned_users,
    postprocess_accept_answer_suggest_edit,
    postprocess_accept_submission_suggestion,
    postprocess_comment_update,
    postprocess_new_answer,
    postprocess_new_answer_suggest_edit,
    postprocess_new_article,
    postprocess_new_comment,
    postprocess_new_feedback,
    postprocess_new_question,
    postprocess_new_submission,
    postprocess_new_submission_suggestion,
    postprocess_updated_article,
    postprocess_updated_question,
    postprocess_updated_submission,
    refresh_interesting_question_ids_for_user,
    refresh_interesting_user_ids_for_user,
)
from chafan_core.app.services.search import refresh_search_index  # noqa: F401
from chafan_core.app.services.viewcounts import write_view_count_to_db  # noqa: F401

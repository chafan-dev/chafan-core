import os

import sentry_sdk
from chafan_core.app import crud
from chafan_core.app.data_broker import DataBroker
from chafan_core.app.feed import cache_new_activity_to_feeds
from chafan_core.app.recs.indexing import (
    index_all_interesting_questions,
    index_all_interesting_users,
)
from chafan_core.app.schemas.audit_log import AUDIT_LOG_API_TYPE
from chafan_core.app.task_utils import execute_with_broker
from chafan_core.app.text_analysis import fill_missing_keywords_task

from chafan_core.scheduled.deliver_notifications import run_deliver_notification_task
from chafan_core.scheduled.lib import cache_matrices, refresh_karmas
from chafan_core.scheduled.refresh_search_index import refresh_search_index

TASK_TO_RUN = os.getenv("TASK_TO_RUN")


def log_task_done(api: AUDIT_LOG_API_TYPE) -> None:
    def f(broker: DataBroker) -> None:
        superuser = crud.user.get_superuser(broker.get_db())
        crud.audit_log.create_with_user(
            broker.get_db(), ipaddr="0.0.0.0", user_id=superuser.id, api=api
        )

    execute_with_broker(f)


if __name__ == "__main__":
    try:
        if TASK_TO_RUN == "run_deliver_notification_task":
            run_deliver_notification_task()
            log_task_done("scheduled/run_deliver_notification_task")
        elif TASK_TO_RUN == "cache_new_activity_to_feeds":
            cache_new_activity_to_feeds()
            cache_matrices()
            log_task_done("scheduled/cache_new_activity_to_feeds")
        elif TASK_TO_RUN == "daily":
            fill_missing_keywords_task()
            refresh_karmas()
            execute_with_broker(index_all_interesting_users)
            execute_with_broker(index_all_interesting_questions)
            log_task_done("scheduled/daily")
        elif TASK_TO_RUN == "refresh_search_index":
            refresh_search_index()
            log_task_done("scheduled/refresh_search_index")
        else:
            raise Exception(f"Uknown task to run: {TASK_TO_RUN}")
    except Exception as e:
        sentry_sdk.capture_exception(e)

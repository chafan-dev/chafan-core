"""APScheduler instance and job registration (Level 5 infra)."""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from chafan_core.app.config import settings

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def set_up_scheduled_tasks() -> None:
    if scheduler.running:
        return
    from chafan_core.app.services.search import refresh_search_index
    from chafan_core.app.services.viewcounts import write_view_count_to_db
    from chafan_core.app.text_analysis import fill_missing_keywords_task

    scheduler.add_job(
        write_view_count_to_db,
        trigger=IntervalTrigger(
            minutes=settings.SCHEDULED_TASK_UPDATE_VIEW_COUNT_MINUTES
        ),
        name="write_view_count_to_db",
    )
    scheduler.add_job(
        refresh_search_index,
        trigger=IntervalTrigger(
            hours=settings.SCHEDULED_TASK_REFRESH_SEARCH_INDEX_HOURS
        ),
        name="refresh_search_index",
    )
    scheduler.add_job(
        fill_missing_keywords_task,
        trigger=IntervalTrigger(
            hours=settings.SCHEDULED_TASK_FILL_MISSING_KEYWORDS_HOURS
        ),
        name="fill_missing_keywords_task",
    )
    # No karma job. Karma is applied as it is earned (see app/karma.py), so
    # there is nothing for a periodic pass to catch up on. `scripts/refresh_karmas.py`
    # recomputes it from scratch on demand -- after a rule change, or to check
    # that no hook is missing.
    # No unread-notification email job. The sender it drove
    # (`app/email_utils.py`) had been a stub returning without sending since
    # the live email path moved to `app/email/`, and it built its unsubscribe
    # link from `settings.SERVER_NAME`, which stopped being a declared setting
    # at the same time -- so every run raised AttributeError into Sentry and
    # delivered nothing. Removed rather than revived: reviving it is a product
    # decision about mailing users again, not a bug fix.
    scheduler.start()
    logger.info("Set up scheduled tasks")

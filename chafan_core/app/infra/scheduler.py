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
    from chafan_core.scheduled.deliver_notifications import run_deliver_notification_task
    from chafan_core.scheduled.lib import refresh_karmas

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
    scheduler.add_job(
        refresh_karmas,
        trigger=IntervalTrigger(hours=settings.SCHEDULED_TASK_REFRESH_KARMAS_HOURS),
        name="refresh_karmas",
    )
    scheduler.add_job(
        run_deliver_notification_task,
        trigger=IntervalTrigger(
            hours=settings.SCHEDULED_TASK_DELIVER_NOTIFICATIONS_HOURS
        ),
        name="run_deliver_notification_task",
    )
    scheduler.start()
    logger.info("Set up scheduled tasks")

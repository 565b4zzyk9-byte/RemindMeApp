import logging

from apscheduler.schedulers.background import BackgroundScheduler

from .digest import send_daily_digests

logger = logging.getLogger(__name__)

_scheduler = None


def init_scheduler(app):
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    scheduler = BackgroundScheduler(timezone=app.config["TIMEZONE"])
    scheduler.add_job(
        func=lambda: send_daily_digests(app),
        trigger="cron",
        day_of_week="mon-fri",
        hour=app.config["DIGEST_HOUR"],
        minute=app.config["DIGEST_MINUTE"],
        id="daily_digest",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        "Scheduler started: daily digest weekdays at %02d:%02d %s",
        app.config["DIGEST_HOUR"],
        app.config["DIGEST_MINUTE"],
        app.config["TIMEZONE"],
    )
    _scheduler = scheduler
    return scheduler

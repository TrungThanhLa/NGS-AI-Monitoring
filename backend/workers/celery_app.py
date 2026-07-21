import os

from celery import Celery

REDIS_URL = os.environ["REDIS_URL"]

celery_app = Celery("ngs_monitor", broker=REDIS_URL, backend=REDIS_URL)

celery_app.conf.beat_schedule = {
    "check-due-sources-every-60s": {
        "task": "scheduler.check_due_sources",
        "schedule": 60.0,
    },
}

from backend.workers import report_job  # noqa: E402,F401  đăng ký task run_report_job
from backend.workers import continuous_crawl  # noqa: E402,F401  đăng ký task crawl_task
from backend.workers import scheduler  # noqa: E402,F401  đăng ký task check_due_sources

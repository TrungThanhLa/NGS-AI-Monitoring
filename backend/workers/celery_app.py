import os

from celery import Celery

REDIS_URL = os.environ["REDIS_URL"]

celery_app = Celery("ngs_monitor", broker=REDIS_URL, backend=REDIS_URL)

from backend.workers import report_job  # noqa: E402,F401  đăng ký task run_report_job

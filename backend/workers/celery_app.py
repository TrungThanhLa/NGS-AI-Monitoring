import os

from celery import Celery

REDIS_URL = os.environ["REDIS_URL"]

celery_app = Celery("ngs_monitor", broker=REDIS_URL, backend=REDIS_URL)


@celery_app.task(name="workers.ping_task")
def ping_task():
    return "pong"

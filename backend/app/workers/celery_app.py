from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "archplan",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.workers.tasks.parse_plan",
        "app.workers.tasks.build_report",
        "app.workers.tasks.extract_loan",
    ],
)

celery_app.conf.task_default_queue = "default"
celery_app.conf.task_routes = {
    "app.workers.tasks.parse_plan.*": {"queue": "parsing"},
    "app.workers.tasks.build_report.*": {"queue": "reports"},
}
celery_app.conf.task_time_limit = 600


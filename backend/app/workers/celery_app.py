"""
=============================================================================
Construtiva Celery & Redis Worker Configuration
=============================================================================
File: app/workers/celery_app.py
Purpose:
  Configures the Celery distributed task queue powered by Redis:
  - Defines queues: 'default', 'parsing' (blueprints), 'reports' (PDF generation).
  - Configures task time limits and serializer settings.
  - Can be started via:
    `celery -A app.workers.celery_app.celery_app worker --loglevel=info -Q default,parsing,reports`
=============================================================================
"""

import logging
from celery import Celery
from app.core.config import settings

logger = logging.getLogger("construtiva.celery")

celery_app = Celery(
    "construtiva_workers",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.workers.tasks.parse_plan",
        "app.workers.tasks.build_report",
        "app.workers.tasks.extract_loan",
    ],
)

celery_app.conf.update(
    task_default_queue="default",
    task_routes={
        "app.workers.tasks.parse_plan.*": {"queue": "parsing"},
        "app.workers.tasks.build_report.*": {"queue": "reports"},
        "app.workers.tasks.extract_loan.*": {"queue": "default"},
    },
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_time_limit=600,  # 10 minute hard ceiling for heavy drawings
    task_soft_time_limit=540,
    worker_prefetch_multiplier=1,
)

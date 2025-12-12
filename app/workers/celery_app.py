"""
Celery application configuration.
"""

from celery import Celery

from app.config import get_settings

settings = get_settings()

# Create Celery app
celery_app = Celery(
    "ai_assistant",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.sync_tasks"],
)

# Configure Celery
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task execution
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max per task
    task_soft_time_limit=3000,  # Soft limit at 50 min

    # Result backend
    result_expires=86400,  # Results expire after 24 hours

    # Worker settings
    worker_prefetch_multiplier=1,
    worker_concurrency=4,

    # Rate limiting
    task_default_rate_limit="10/m",

    # Task routes
    task_routes={
        "app.workers.sync_tasks.initial_sync_task": {"queue": "sync"},
        "app.workers.sync_tasks.sync_gmail_task": {"queue": "sync"},
        "app.workers.sync_tasks.sync_gdrive_task": {"queue": "sync"},
        "app.workers.sync_tasks.sync_jira_task": {"queue": "sync"},
        "app.workers.sync_tasks.sync_calendar_task": {"queue": "sync"},
    },

    # Beat schedule for periodic tasks
    beat_schedule={
        "incremental-sync-every-hour": {
            "task": "app.workers.sync_tasks.periodic_sync",
            "schedule": 3600.0,  # Every hour
        },
    },
)

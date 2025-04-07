"""
Celery application configuration.
"""
from celery import Celery
from ..config.settings import settings

# Create Celery instance
app = Celery('ticket_tracker')

# Configure Celery
app.conf.update(
    broker_url="redis://127.0.0.1:6379/0",  # Explicitly use 127.0.0.1 instead of settings
    result_backend="redis://127.0.0.1:6379/1",  # Explicitly use 127.0.0.1 instead of settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    worker_hijack_root_logger=False,  # Don't hijack root logger
    worker_redirect_stdouts=False,    # Don't redirect stdout/stderr
    task_always_eager=False,          # Don't run tasks eagerly in the same process
    task_create_missing_queues=True,  # Create queues at runtime if they don't exist
    task_default_queue='celery',      # Default queue name
    worker_prefetch_multiplier=1,     # Prefetch only one task at a time to avoid overloading
    task_acks_late=True,              # Acknowledge tasks after they are executed
)

# Auto-discover tasks in specified modules
app.autodiscover_tasks(['src.tasks.event_tasks', 'src.tasks.listing_tasks'])

# This will import all tasks when this module is imported
if __name__ == '__main__':
    app.start()
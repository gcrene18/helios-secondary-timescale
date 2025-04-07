"""
Custom Celery Beat scheduler with randomization support.
"""
from celery.beat import Scheduler
from celery import current_app
from celery.schedules import schedule
from datetime import datetime, timedelta
import time
import pickle
import shelve
from pathlib import Path

from ..scheduler.randomizer import RandomizationStrategy
from ..core.logging import get_logger

logger = get_logger(__name__)

class RandomizedScheduleEntry(schedule):
    """
    Schedule entry that supports randomized intervals.
    """
    def __init__(self, 
                 base_interval_hours=None, 
                 strategy='uniform',
                 **kwargs):
        self.base_interval_hours = base_interval_hours
        self.strategy = strategy
        self.last_run_at = None
        
        # Calculate initial interval
        if base_interval_hours:
            interval = RandomizationStrategy.calculate_next_interval(
                base_interval_hours, strategy
            )
            # Convert timedelta to seconds for schedule
            kwargs['run_every'] = interval.total_seconds()
        
        super().__init__(**kwargs)
        
    def is_due(self):
        """Return tuple of (is_due, next_time_in_seconds)."""
        now = datetime.now()
        if not self.last_run_at:
            # First run
            self.last_run_at = now
            return True, 0
            
        # Get result from parent
        is_due, next_time = super().is_due()
        
        if is_due:
            # Task is due, calculate next randomized interval
            if self.base_interval_hours:
                interval = RandomizationStrategy.calculate_next_interval(
                    self.base_interval_hours, self.strategy
                )
                self.run_every = interval.total_seconds()
                logger.info(
                    f"Randomized next run interval",
                    task=self.name,
                    base_hours=self.base_interval_hours,
                    strategy=self.strategy,
                    next_interval_seconds=self.run_every
                )
            
            self.last_run_at = now
            
        return is_due, next_time
        
    def __reduce__(self):
        """For pickling."""
        return (self.__class__, (
            self.base_interval_hours,
            self.strategy,
        ), {
            'run_every': self.run_every,
            'last_run_at': self.last_run_at,
        })

class RandomizedScheduler(Scheduler):
    """
    Celery Beat scheduler that supports randomized intervals.
    """
    def __init__(self, *args, **kwargs):
        self.data_dir = kwargs.pop('data_dir', None)
        if self.data_dir:
            self.data_dir = Path(self.data_dir)
            self.data_dir.mkdir(exist_ok=True)
            kwargs['schedule_filename'] = str(self.data_dir / "celerybeat-schedule")
            
        super().__init__(*args, **kwargs)
        
    def setup_schedule(self):
        """Set up the schedule."""
        super().setup_schedule()
        
        # Add our custom randomized tasks
        from ..config.settings import settings
        
        # Get base scrape interval from settings
        base_interval = settings.base_scrape_interval_hours
        strategy = settings.default_randomization_strategy
        
        self.app.conf.beat_schedule = {
            'fetch-events-daily': {
                'task': 'src.tasks.event_tasks.fetch_events',
                'schedule': RandomizedScheduleEntry(
                    base_interval_hours=24.0,  # Daily
                    strategy='uniform'
                ),
            },
            'fetch-outdated-listings': {
                'task': 'src.tasks.listing_tasks.fetch_outdated_listings',
                'schedule': RandomizedScheduleEntry(
                    base_interval_hours=base_interval,
                    strategy=strategy
                ),
                'kwargs': {'hours': 12},
            },
        }
        
        # Update scheduler entries
        self.install_default_entries(self.app.conf.beat_schedule)
        
    def reserve(self, entry):
        """Reserve a task entry."""
        # Log the next run time for our custom entries
        if isinstance(entry.schedule, RandomizedScheduleEntry):
            logger.info(
                f"Scheduled task {entry.name}",
                next_run=entry.next,
                interval_seconds=entry.schedule.run_every
            )
        return super().reserve(entry)
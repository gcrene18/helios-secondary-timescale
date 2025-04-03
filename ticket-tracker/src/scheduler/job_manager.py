"""
Job management and scheduling logic.
"""
import asyncio
import schedule
import time
from typing import Dict, Any, List, Callable, Optional
from datetime import datetime, timedelta
import threading

from ..core.logging import get_logger, console
from ..config.settings import settings
from ..scheduler.randomizer import RandomizationStrategy
from rich.panel import Panel
from rich.table import Table

logger = get_logger(__name__)

class Job:
    """
    Represents a scheduled job with metadata.
    
    This class stores information about a scheduled job,
    including its timing, status, and execution history.
    """
    
    def __init__(
        self, 
        name: str, 
        func: Callable, 
        interval_hours: float,
        randomization_strategy: str = 'uniform'
    ):
        """
        Initialize a job.
        
        Args:
            name: Name of the job
            func: Function to execute
            interval_hours: Base interval in hours
            randomization_strategy: Strategy for randomizing intervals
        """
        self.name = name
        self.func = func
        self.base_interval_hours = interval_hours
        self.randomization_strategy = randomization_strategy
        self.last_run: Optional[datetime] = None
        self.next_run: Optional[datetime] = None
        self.run_count = 0
        self.status = "scheduled"
        self.error = None
        
    def execute(self):
        """Execute the job function and update metadata."""
        self.status = "running"
        self.last_run = datetime.now()
        self.run_count += 1
        
        try:
            logger.info(f"Executing job: {self.name}")
            result = self.func()
            self.status = "completed"
            self.error = None
            return result
        except Exception as e:
            self.status = "failed"
            self.error = str(e)
            logger.error(f"Job {self.name} failed", error=str(e))
            return None
        finally:
            # Calculate next run time
            self._schedule_next_run()
    
    def _schedule_next_run(self):
        """Calculate and set the next run time using randomization."""
        interval = RandomizationStrategy.calculate_next_interval(
            self.base_interval_hours, 
            self.randomization_strategy
        )
        
        self.next_run = datetime.now() + interval
        
        logger.info(
            f"Next run for job {self.name} scheduled",
            next_run=self.next_run.isoformat(),
            interval_hours=interval.total_seconds() / 3600
        )
    
    def __str__(self) -> str:
        """String representation of the job."""
        next_run_str = self.next_run.strftime("%Y-%m-%d %H:%M:%S") if self.next_run else "Not scheduled"
        last_run_str = self.last_run.strftime("%Y-%m-%d %H:%M:%S") if self.last_run else "Never"
        
        return (f"Job: {self.name} | Status: {self.status} | "
                f"Last run: {last_run_str} | Next run: {next_run_str}")


class JobManager:
    """
    Manages scheduled jobs with intelligent randomization.
    
    This class handles job scheduling, execution, and monitoring
    with built-in randomization to avoid detection during scraping.
    """
    
    def __init__(self):
        """Initialize the job manager."""
        self.jobs: Dict[str, Job] = {}
        self.scheduler = schedule
        self.running = False
        self.scheduler_thread = None
        
    def add_job(
        self, 
        name: str, 
        func: Callable, 
        interval_hours: float = None,
        randomization_strategy: str = 'uniform'
    ) -> Job:
        """
        Add a new job to the manager.
        
        Args:
            name: Unique name for the job
            func: Function to execute
            interval_hours: Base interval in hours (default from settings)
            randomization_strategy: Strategy for randomizing intervals
            
        Returns:
            The created Job instance
        """
        interval_hours = interval_hours or settings.base_scrape_interval_hours
        
        # Create the job
        job = Job(name, func, interval_hours, randomization_strategy)
        
        # Set initial next run time
        job._schedule_next_run()
        
        # Store the job
        self.jobs[name] = job
        
        logger.info(
            f"Added job {name}",
            interval=interval_hours,
            strategy=randomization_strategy,
            next_run=job.next_run.isoformat()
        )
        
        return job
    
    def remove_job(self, name: str) -> bool:
        """
        Remove a job from the manager.
        
        Args:
            name: Name of the job to remove
            
        Returns:
            True if job was removed, False if not found
        """
        if name in self.jobs:
            del self.jobs[name]
            logger.info(f"Removed job {name}")
            return True
        
        logger.warning(f"Job {name} not found for removal")
        return False
    
    def _run_pending_jobs(self):
        """Check for and run any jobs that are due."""
        now = datetime.now()
        
        for name, job in list(self.jobs.items()):
            if job.next_run and job.next_run <= now:
                logger.info(f"Job {name} is due, executing...")
                job.execute()
    
    def start(self):
        """Start the job manager in a separate thread."""
        if self.running:
            logger.warning("Job manager is already running")
            return
        
        self.running = True
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.scheduler_thread.start()
        
        logger.info("Job manager started")
    
    def _scheduler_loop(self):
        """Main scheduler loop that runs in a separate thread."""
        logger.info("Scheduler loop started")
        
        while self.running:
            self._run_pending_jobs()
            time.sleep(1)  # Check every second
    
    def stop(self):
        """Stop the job manager."""
        if not self.running:
            logger.warning("Job manager is not running")
            return
        
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        
        logger.info("Job manager stopped")
    
    def get_job_status(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get the status of a specific job.
        
        Args:
            name: Name of the job
            
        Returns:
            Dictionary with job status information, or None if job not found
        """
        job = self.jobs.get(name)
        
        if not job:
            return None
            
        return {
            'name': job.name,
            'status': job.status,
            'last_run': job.last_run,
            'next_run': job.next_run,
            'run_count': job.run_count,
            'error': job.error
        }
    
    def get_all_job_statuses(self) -> List[Dict[str, Any]]:
        """
        Get status information for all jobs.
        
        Returns:
            List of dictionaries with job status information
        """
        return [self.get_job_status(name) for name in self.jobs]
    
    def generate_status_table(self) -> Table:
        """
        Generate a rich table with job status information.
        
        Returns:
            Rich Table object for display
        """
        table = Table(title="Job Status")
        
        table.add_column("Job Name", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Last Run", style="yellow")
        table.add_column("Next Run", style="blue")
        table.add_column("Run Count", style="magenta")
        
        for name, job in self.jobs.items():
            last_run = job.last_run.strftime("%Y-%m-%d %H:%M:%S") if job.last_run else "Never"
            next_run = job.next_run.strftime("%Y-%m-%d %H:%M:%S") if job.next_run else "Not scheduled"
            
            status_style = {
                "scheduled": "green",
                "running": "yellow",
                "completed": "green",
                "failed": "red"
            }.get(job.status, "white")
            
            table.add_row(
                job.name,
                f"[{status_style}]{job.status}[/{status_style}]",
                last_run,
                next_run,
                str(job.run_count)
            )
        
        return table
    
    def print_status(self):
        """Print a status table to the console."""
        status_table = self.generate_status_table()
        console.print(Panel(status_table, title="Job Manager Status", border_style="blue"))


# Global job manager instance
job_manager = JobManager()

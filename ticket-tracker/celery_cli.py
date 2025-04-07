#!/usr/bin/env python3
"""
Command-line interface for Celery tasks in the Ticket Tracker application.
"""
import os
import sys
import subprocess
from pathlib import Path
import typer
from rich.console import Console
from rich.panel import Panel
from typing import List

# Add the current directory to the path so we can import from src
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.config.settings import settings
from src.core.logging import console, configure_logging

# Initialize logging
logger = configure_logging()

# Create Typer app
app = typer.Typer(
    name="celery-cli",
    help="Celery task management for Ticket Tracker",
    add_completion=False
)


def print_header():
    """Print application header."""
    console.print(Panel(
        f"[bold blue]Ticket Tracker Celery Manager[/bold blue]\n"
        f"[dim]Manage Celery workers and tasks[/dim]",
        border_style="blue"
    ))


@app.command()
def worker(
    log_level: str = typer.Option("INFO", help="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)")
):
    """Start the Celery worker for processing tasks."""
    print_header()
    console.print("[bold green]Starting Celery worker...[/bold green]")
    
    # Prepare worker command
    worker_cmd = [
        "celery", 
        "-A", "src.tasks.celery_app", 
        "worker",
        "--loglevel", log_level,
        f"--concurrency={settings.celery_worker_concurrency}",
        f"--time-limit={settings.celery_task_time_limit}",
        f"--soft-time-limit={settings.celery_task_soft_time_limit}"
    ]
    
    # Execute the worker
    subprocess.run(worker_cmd)


@app.command()
def beat():
    """Start the Celery beat scheduler for periodic tasks."""
    print_header()
    console.print("[bold green]Starting Celery beat scheduler...[/bold green]")
    
    # Create schedule directory if it doesn't exist
    os.makedirs(settings.celery_beat_schedule_dir, exist_ok=True)
    
    # Prepare beat command
    beat_cmd = [
        "celery", 
        "-A", "src.tasks.celery_app", 
        "beat",
        "--loglevel=info",
        f"--scheduler={settings.celery_beat_scheduler}",
        f"--schedule={os.path.join(settings.celery_beat_schedule_dir, 'celerybeat-schedule')}"
    ]
    
    # Execute the beat scheduler
    subprocess.run(beat_cmd)


@app.command()
def flower():
    """Start the Flower monitoring dashboard for Celery."""
    print_header()
    console.print("[bold green]Starting Flower monitoring dashboard...[/bold green]")
    
    # Prepare flower command
    flower_cmd = [
        "celery", 
        "-A", "src.tasks.celery_app", 
        "flower",
        "--port=5555",
        f"--broker={settings.celery_broker_url}"
    ]
    
    # Execute flower
    subprocess.run(flower_cmd)


@app.command()
def status():
    """Show status of Celery workers and tasks."""
    print_header()
    console.print("[bold green]Checking Celery status...[/bold green]")
    
    # Prepare status command
    status_cmd = [
        "celery", 
        "-A", "src.tasks.celery_app", 
        "status"
    ]
    
    # Execute status command
    subprocess.run(status_cmd)


@app.command()
def run_task(task_name: str):
    """Run a specific Celery task."""
    console.print(f"Running task: {task_name}")
    
    # Import tasks here to ensure they are registered
    import src.tasks.event_tasks
    import src.tasks.listing_tasks
    
    # Get the task by name
    if task_name == "src.tasks.event_tasks.fetch_events":
        task = src.tasks.event_tasks.fetch_events
    elif task_name == "src.tasks.listing_tasks.fetch_all_listings":
        task = src.tasks.listing_tasks.fetch_all_listings
    elif task_name == "src.tasks.listing_tasks.fetch_listings_for_event":
        task = src.tasks.listing_tasks.fetch_listings_for_event
    elif task_name == "src.tasks.listing_tasks.fetch_outdated_listings":
        task = src.tasks.listing_tasks.fetch_outdated_listings
    elif task_name == "src.tasks.listing_tasks.debug_database_connection":
        task = src.tasks.listing_tasks.debug_database_connection
    elif task_name == "src.tasks.listing_tasks.debug_simple":
        task = src.tasks.listing_tasks.debug_simple
    else:
        console.print(f"[bold red]Error: Task '{task_name}' not found[/bold red]")
        return
    
    try:
        # Run the task directly (not through Celery) to debug issues
        if task_name == "src.tasks.listing_tasks.fetch_all_listings":
            # Special handling for fetch_all_listings due to the NoneType error
            from src.infrastructure.database.event_repo import EventRepository
            
            # Get tracked events directly
            events = EventRepository.get_tracked()
            if events is None:
                console.print("[bold red]Error: get_tracked() returned None[/bold red]")
                return
                
            event_count = len(events) if events else 0
            console.print(f"Retrieved {event_count} tracked events")
            
            # Process each event
            task_count = 0
            for event in events:
                if not hasattr(event, 'viagogo_id') or not event.viagogo_id:
                    console.print(f"Skipping event with missing viagogo_id: {event.name if hasattr(event, 'name') else 'Unknown'}")
                    continue
                
                # Queue a task for each event using Celery
                result = src.tasks.listing_tasks.fetch_listings_for_event.delay(event.viagogo_id)
                console.print(f"Scheduled task for event {event.name} (ID: {event.viagogo_id})")
                task_count += 1
            
            console.print(f"[bold green]Successfully scheduled {task_count} tasks[/bold green]")
        else:
            # For other tasks, run them through Celery
            result = task.delay()
            console.print(f"Task submitted with ID: {result.id}")
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}[/bold red]")
        import traceback
        console.print(traceback.format_exc())


if __name__ == "__main__":
    app()

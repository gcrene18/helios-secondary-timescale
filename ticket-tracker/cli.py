#!/usr/bin/env python3
"""
Command-line interface for the Ticket Tracker application.
"""
import asyncio
import typer
import time
from typing import Optional, List
from pathlib import Path
import sys
import os
from rich.console import Console
from rich.panel import Panel
from rich.layout import Layout
from rich.table import Table
from datetime import datetime, timedelta

# Add the current directory to the path so we can import from src
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.core.logging import console, configure_logging, get_logger
from src.config.settings import settings
from src.core.db import db
from src.data.google_sheets import GoogleSheetsClient
from src.data.stubhub import StubHubClient
from src.domain.event import Event
from src.domain.listing import Listing
from src.infrastructure.database.event_repo import EventRepository
from src.infrastructure.database.listing_repo import ListingRepository
from src.infrastructure.services.google_api import GoogleSheetsService
from src.infrastructure.services.stubhub_api import StubHubService
from src.scheduler.job_manager import job_manager
from src.scheduler.randomizer import RandomizationStrategy

# Initialize logging
logger = configure_logging()

# Create Typer app
app = typer.Typer(
    name="ticket-tracker",
    help="Secondary ticket market data tracking system",
    add_completion=False
)


def print_header():
    """Print application header."""
    console.print(Panel(
        f"[bold blue]Secondary Ticket Data Tracker v{settings.version}[/bold blue]\n"
        f"[dim]Collecting price data from secondary ticket markets[/dim]",
        border_style="blue"
    ))


@app.command()
def init_db():
    """Initialize database tables and extensions."""
    print_header()
    console.print("[bold yellow]Initializing database...[/bold yellow]")
    
    try:
        # Initialize TimescaleDB extension
        db.initialize_timescale()
        
        # Create tables
        EventRepository.ensure_table_exists()
        ListingRepository.ensure_table_exists()
        
        console.print("[bold green]Database initialization complete![/bold green]")
    except Exception as e:
        console.print(f"[bold red]Database initialization failed: {e}[/bold red]")
        raise typer.Exit(code=1)


@app.command()
def fetch_events():
    """Fetch events from Google Sheet and store in database."""
    print_header()
    console.print("[bold yellow]Fetching events from Google Sheet...[/bold yellow]")
    
    try:
        # Create Google Sheets service
        sheets_service = GoogleSheetsService()
        
        # Fetch events
        events = sheets_service.fetch_events()
        
        if not events:
            console.print("[bold yellow]No events found in Google Sheet[/bold yellow]")
            return
        
        # Display events
        event_table = Table(title=f"Found {len(events)} Events")
        event_table.add_column("Name", style="cyan")
        event_table.add_column("Venue", style="green")
        event_table.add_column("City", style="blue")
        event_table.add_column("Country", style="magenta")
        event_table.add_column("Date", style="yellow")
        event_table.add_column("viagogoID", style="dim")
        
        for event in events:
            event_date = event.event_date.strftime("%Y-%m-%d %H:%M") if event.event_date else "Unknown"
            event_table.add_row(
                event.name,
                event.venue,
                event.city,
                event.country,
                event_date,
                event.viagogo_id
            )
        
        console.print(event_table)
        
        # Sync events to database
        console.print("[bold yellow]Syncing events to database...[/bold yellow]")
        stats = EventRepository.sync_from_google_sheets(events)
        
        console.print(f"[bold green]Event sync complete:[/bold green] "
                      f"{stats['inserted']} inserted, {stats['updated']} updated, "
                      f"{stats['failed']} failed")
        
    except Exception as e:
        console.print(f"[bold red]Error fetching events: {e}[/bold red]")
        raise typer.Exit(code=1)


@app.command()
def fetch_listings(
    viagogo_id: Optional[str] = typer.Argument(
        None, help="viagogo ID of the event to fetch listings for. If not provided, fetches all events."
    )
):
    """Fetch ticket listings from StubHub and store in database."""
    print_header()
    
    async def run():
        try:
            # Create services
            stubhub_service = StubHubService()
            
            if viagogo_id:
                # Fetch listings for a single event
                console.print(f"[bold yellow]Fetching listings for event with viagogo ID: {viagogo_id}[/bold yellow]")
                
                # Check if event exists in database
                event = EventRepository.get_by_viagogo_id(viagogo_id)
                
                if not event:
                    console.print(f"[bold red]Event with viagogo ID {viagogo_id} not found in database[/bold red]")
                    return
                
                # Fetch and store listings
                count = await stubhub_service.fetch_and_store_listings(event)
                
                console.print(f"[bold green]Stored {count} listings for event: {event.name}[/bold green]")
            
            else:
                # Fetch listings for all events
                console.print("[bold yellow]Fetching listings for all events...[/bold yellow]")
                
                # Get all events from database
                events = EventRepository.get_all()
                
                if not events:
                    console.print("[bold yellow]No events found in database[/bold yellow]")
                    return
                
                # Fetch and store listings for all events
                results = await stubhub_service.fetch_all_events_listings(events)
                
                # Display results
                total_listings = sum(results.values())
                events_with_listings = sum(1 for count in results.values() if count > 0)
                
                console.print(f"[bold green]Completed fetching listings:[/bold green] "
                             f"Found listings for {events_with_listings}/{len(events)} events, "
                             f"Stored {total_listings} total listings")
        
        except Exception as e:
            console.print(f"[bold red]Error fetching listings: {e}[/bold red]")
            raise typer.Exit(code=1)
    
    # Run the async function
    asyncio.run(run())


@app.command()
def fetch_outdated_listings(
    hours: int = typer.Option(
        12, help="Fetch listings for events not updated in this many hours"
    )
):
    """Fetch ticket listings for events that haven't been updated in the specified hours."""
    print_header()
    
    async def run():
        try:
            console.print(f"[bold yellow]Fetching listings for events not updated in the last {hours} hours...[/bold yellow]")
            
            # Create StubHub service
            stubhub_service = StubHubService()
            
            # Fetch listings for events needing updates
            results = await stubhub_service.fetch_events_needing_update(hours)
            
            if not results:
                console.print("[bold yellow]No events found needing updates[/bold yellow]")
                return
            
            # Display results
            total_listings = sum(results.values())
            events_with_listings = sum(1 for count in results.values() if count > 0)
            
            console.print(f"[bold green]Completed fetching listings for outdated events:[/bold green] "
                         f"Found listings for {events_with_listings}/{len(results)} events, "
                         f"Stored {total_listings} total listings")
        
        except Exception as e:
            console.print(f"[bold red]Error fetching listings for outdated events: {e}[/bold red]")
            raise typer.Exit(code=1)
    
    # Run the async function
    asyncio.run(run())


@app.command()
def show_events():
    """Display events stored in the database."""
    print_header()
    console.print("[bold yellow]Retrieving events from database...[/bold yellow]")
    
    try:
        # Get all events from database
        events = EventRepository.get_all()
        
        if not events:
            console.print("[bold yellow]No events found in database[/bold yellow]")
            return
        
        # Display events
        event_table = Table(title=f"Found {len(events)} Events")
        event_table.add_column("ID", style="dim")
        event_table.add_column("Name", style="cyan")
        event_table.add_column("Venue", style="green")
        event_table.add_column("City", style="blue")
        event_table.add_column("Country", style="magenta")
        event_table.add_column("Date", style="yellow")
        event_table.add_column("viagogoID", style="dim")
        
        for event in events:
            event_date = event.event_date.strftime("%Y-%m-%d %H:%M") if event.event_date else "Unknown"
            event_table.add_row(
                str(event.event_id),
                event.name,
                event.venue,
                event.city,
                event.country,
                event_date,
                event.viagogo_id
            )
        
        console.print(event_table)
        
    except Exception as e:
        console.print(f"[bold red]Error retrieving events: {e}[/bold red]")
        raise typer.Exit(code=1)


@app.command()
def show_listings(
    event_id: int = typer.Argument(..., help="ID of the event to show listings for"),
    limit: int = typer.Option(20, help="Maximum number of listings to show")
):
    """Display ticket listings for an event."""
    print_header()
    console.print(f"[bold yellow]Retrieving listings for event ID: {event_id}[/bold yellow]")
    
    try:
        # Check if event exists
        event = EventRepository.get_by_id(event_id)
        
        if not event:
            console.print(f"[bold red]Event with ID {event_id} not found[/bold red]")
            return
        
        # Get listings
        listings = ListingRepository.get_latest_listings(event_id, limit)
        
        if not listings:
            console.print(f"[bold yellow]No listings found for event: {event.name}[/bold yellow]")
            return
        
        # Display event info
        console.print(Panel(
            f"[bold cyan]{event.name}[/bold cyan]\n"
            f"[green]{event.venue}, {event.city}, {event.country}[/green]\n"
            f"[yellow]Date: {event.event_date.strftime('%Y-%m-%d %H:%M')}[/yellow]",
            title="Event Information",
            border_style="blue"
        ))
        
        # Display listings
        listing_table = Table(title=f"Latest {len(listings)} Listings")
        listing_table.add_column("Section", style="cyan")
        listing_table.add_column("Row", style="green")
        listing_table.add_column("Qty", style="blue", justify="right")
        listing_table.add_column("Price/Ticket", style="yellow", justify="right")
        listing_table.add_column("Total", style="magenta", justify="right")
        listing_table.add_column("Currency", style="dim")
        listing_table.add_column("Captured At", style="dim")
        
        for listing in listings:
            listing_table.add_row(
                listing.section,
                listing.row or "N/A",
                str(listing.quantity),
                f"{listing.price_per_ticket:.2f}",
                f"{listing.total_price:.2f}",
                listing.currency,
                listing.captured_at.strftime("%Y-%m-%d %H:%M:%S")
            )
        
        console.print(listing_table)
        
    except Exception as e:
        console.print(f"[bold red]Error retrieving listings: {e}[/bold red]")
        raise typer.Exit(code=1)


@app.command()
def price_history(
    event_id: int = typer.Argument(..., help="ID of the event to show price history for"),
    days: int = typer.Option(30, help="Number of days to look back"),
    bucket: str = typer.Option("1 day", help="Time bucket size (e.g., '1 hour', '1 day')")
):
    """Display ticket price history for an event."""
    print_header()
    console.print(f"[bold yellow]Retrieving price history for event ID: {event_id}[/bold yellow]")
    
    try:
        # Check if event exists
        event = EventRepository.get_by_id(event_id)
        
        if not event:
            console.print(f"[bold red]Event with ID {event_id} not found[/bold red]")
            return
        
        # Get price history
        price_history = ListingRepository.get_price_history(event_id, bucket, days)
        
        if not price_history:
            console.print(f"[bold yellow]No price history found for event: {event.name}[/bold yellow]")
            return
        
        # Display event info
        console.print(Panel(
            f"[bold cyan]{event.name}[/bold cyan]\n"
            f"[green]{event.venue}, {event.city}, {event.country}[/green]\n"
            f"[yellow]Date: {event.event_date.strftime('%Y-%m-%d %H:%M')}[/yellow]",
            title="Event Information",
            border_style="blue"
        ))
        
        # Display price history
        history_table = Table(title=f"Price History (Past {days} days, {bucket} intervals)")
        history_table.add_column("Date", style="cyan")
        history_table.add_column("Min", style="green", justify="right")
        history_table.add_column("Avg", style="yellow", justify="right")
        history_table.add_column("Max", style="red", justify="right")
        history_table.add_column("Listings", style="blue", justify="right")
        
        for point in price_history:
            bucket_date = point['bucket'].strftime("%Y-%m-%d %H:%M")
            history_table.add_row(
                bucket_date,
                f"${point['min_price']:.2f}",
                f"${point['avg_price']:.2f}",
                f"${point['max_price']:.2f}",
                str(point['listing_count'])
            )
        
        console.print(history_table)
        
    except Exception as e:
        console.print(f"[bold red]Error retrieving price history: {e}[/bold red]")
        raise typer.Exit(code=1)


@app.command()
def section_prices(
    event_id: int = typer.Argument(..., help="ID of the event to show section prices for"),
    days: int = typer.Option(7, help="Number of days to look back")
):
    """Display ticket prices by section for an event."""
    print_header()
    console.print(f"[bold yellow]Retrieving section prices for event ID: {event_id}[/bold yellow]")
    
    try:
        # Check if event exists
        event = EventRepository.get_by_id(event_id)
        
        if not event:
            console.print(f"[bold red]Event with ID {event_id} not found[/bold red]")
            return
        
        # Get section prices
        section_prices = ListingRepository.get_price_by_section(event_id, days)
        
        if not section_prices:
            console.print(f"[bold yellow]No section prices found for event: {event.name}[/bold yellow]")
            return
        
        # Display event info
        console.print(Panel(
            f"[bold cyan]{event.name}[/bold cyan]\n"
            f"[green]{event.venue}, {event.city}, {event.country}[/green]\n"
            f"[yellow]Date: {event.event_date.strftime('%Y-%m-%d %H:%M')}[/yellow]",
            title="Event Information",
            border_style="blue"
        ))
        
        # Display section prices
        section_table = Table(title=f"Prices by Section (Past {days} days)")
        section_table.add_column("Section", style="cyan")
        section_table.add_column("Avg Price", style="yellow", justify="right")
        section_table.add_column("Min Price", style="green", justify="right")
        section_table.add_column("Max Price", style="red", justify="right")
        section_table.add_column("Listings", style="blue", justify="right")
        section_table.add_column("Latest Update", style="dim")
        
        for section in section_prices:
            latest_update = section['latest_capture'].strftime("%Y-%m-%d %H:%M")
            section_table.add_row(
                section['section'],
                f"${section['avg_price']:.2f}",
                f"${section['min_price']:.2f}",
                f"${section['max_price']:.2f}",
                str(section['listing_count']),
                latest_update
            )
        
        console.print(section_table)
        
    except Exception as e:
        console.print(f"[bold red]Error retrieving section prices: {e}[/bold red]")
        raise typer.Exit(code=1)


@app.command()
def start_scheduler(
    interval_hours: Optional[float] = typer.Option(
        None, help="Override the base scrape interval in hours"
    ),
    randomization: str = typer.Option(
        "poisson", help="Randomization strategy: 'uniform', 'poisson', or 'normal'"
    )
):
    """Start the scheduler to periodically fetch listings."""
    print_header()
    console.print("[bold yellow]Starting ticket data collection scheduler...[/bold yellow]")
    
    # Use provided interval or default from settings
    base_interval = interval_hours or settings.base_scrape_interval_hours
    
    try:
        # Define the job function
        async def fetch_all_listings_job():
            """Job to fetch listings for all events."""
            try:
                # Get all events from database
                events = EventRepository.get_all()
                
                if not events:
                    logger.warning("No events found in database for scheduled job")
                    return
                
                # Create StubHub service
                stubhub_service = StubHubService()
                
                # Fetch and store listings for all events
                results = await stubhub_service.fetch_all_events_listings(events)
                
                # Log results
                total_listings = sum(results.values())
                events_with_listings = sum(1 for count in results.values() if count > 0)
                
                logger.info(
                    f"Scheduled job completed: Found listings for {events_with_listings}/{len(events)} events, "
                    f"Stored {total_listings} total listings"
                )
                
                return results
            
            except Exception as e:
                logger.error(f"Error in scheduled job: {e}")
                return None
        
        # Create a wrapper to run the async job
        def run_listings_job():
            """Run the async listings job."""
            return asyncio.run(fetch_all_listings_job())
        
        # Add the job to the scheduler
        job_manager.add_job(
            name="fetch_listings",
            func=run_listings_job,
            interval_hours=base_interval,
            randomization_strategy=randomization
        )
        
        # Start the job manager
        job_manager.start()
        
        # Show job schedule
        job_manager.print_status()
        
        console.print(
            f"\n[bold green]Scheduler started with {randomization} randomization[/bold green]\n"
            f"Base interval: [yellow]{base_interval} hours[/yellow]\n"
            f"Press Ctrl+C to stop...\n"
        )
        
        # Keep the main thread running
        try:
            while True:
                time.sleep(10)
                # Update status every minute
                if int(time.time()) % 60 < 10:
                    job_manager.print_status()
        except KeyboardInterrupt:
            console.print("\n[bold yellow]Stopping scheduler...[/bold yellow]")
            job_manager.stop()
            console.print("[bold green]Scheduler stopped[/bold green]")
    
    except Exception as e:
        console.print(f"[bold red]Error starting scheduler: {e}[/bold red]")
        raise typer.Exit(code=1)


@app.command()
def cleanup_untracked_events(
    dry_run: bool = typer.Option(
        True, help="Show what would be done without making changes"
    ),
    delete: bool = typer.Option(
        False, help="Delete untracked events instead of just marking them as untracked"
    )
):
    """Remove or mark events that are no longer tracked in Google Sheets."""
    print_header()
    console.print("[bold yellow]Cleaning up untracked events...[/bold yellow]")
    
    try:
        # Create Google Sheets service and fetch all events (including untracked)
        sheets_service = GoogleSheetsService()
        all_sheet_events = sheets_service.fetch_events()
        
        # Get all events from database
        db_events = EventRepository.get_all()
        
        # Map viagogo IDs to tracking status from Google Sheets
        tracking_status = {event.viagogo_id: event.is_tracked for event in all_sheet_events}
        
        # Find events in database that are not tracked in sheets
        untracked_events = []
        for db_event in db_events:
            # If event exists in sheets and is marked as not tracked, or if it no longer exists in sheets
            if db_event.viagogo_id in tracking_status:
                if not tracking_status[db_event.viagogo_id]:
                    untracked_events.append(db_event)
            # Optionally handle events that are no longer in the sheet at all
            # else:
            #    untracked_events.append(db_event)
        
        if not untracked_events:
            console.print("[bold green]No untracked events found in database.[/bold green]")
            return
        
        # Display untracked events
        event_table = Table(title=f"Found {len(untracked_events)} Untracked Events")
        event_table.add_column("ID", style="dim")
        event_table.add_column("Name", style="cyan")
        event_table.add_column("Venue", style="green")
        event_table.add_column("Date", style="yellow")
        event_table.add_column("viagogoID", style="dim")
        
        for event in untracked_events:
            event_date = event.event_date.strftime("%Y-%m-%d %H:%M") if event.event_date else "Unknown"
            event_table.add_row(
                str(event.event_id),
                event.name,
                event.venue,
                event_date,
                event.viagogo_id
            )
        
        console.print(event_table)
        
        if dry_run:
            console.print("[bold yellow]Dry run - no changes made. Use --no-dry-run to apply changes.[/bold yellow]")
            return
        
        # Process untracked events
        deleted_count = 0
        updated_count = 0
        
        for event in untracked_events:
            if delete:
                if EventRepository.delete(event.event_id):
                    deleted_count += 1
            else:
                # Mark as untracked in database
                event.is_tracked = False
                if EventRepository.update(event):
                    updated_count += 1
        
        if delete:
            console.print(f"[bold green]Cleanup complete: {deleted_count} events deleted[/bold green]")
        else:
            console.print(f"[bold green]Cleanup complete: {updated_count} events marked as untracked[/bold green]")
        
    except Exception as e:
        console.print(f"[bold red]Error during cleanup: {e}[/bold red]")
        raise typer.Exit(code=1)


@app.command()
def run():
    """Run the full ticket tracking system."""
    print_header()
    console.print("[bold yellow]Starting Ticket Tracker...[/bold yellow]")
    
    try:
        # Initialize database
        console.print("[bold blue]Step 1: Initializing database...[/bold blue]")
        db.initialize_timescale()
        EventRepository.ensure_table_exists()
        ListingRepository.ensure_table_exists()
        console.print("[bold green]Database initialized![/bold green]")
        
        # Fetch events from Google Sheets
        console.print("\n[bold blue]Step 2: Fetching events from Google Sheets...[/bold blue]")
        sheets_service = GoogleSheetsService()
        events = sheets_service.fetch_events()
        
        if events:
            console.print(f"[bold green]Found {len(events)} events![/bold green]")
            stats = EventRepository.sync_from_google_sheets(events)
            console.print(f"Event sync complete: {stats['inserted']} inserted, "
                         f"{stats['updated']} updated, {stats['failed']} failed")
        else:
            console.print("[bold red]No events found in Google Sheets[/bold red]")
            return
        
        # Fetch initial listings
        console.print("\n[bold blue]Step 3: Fetching initial listings...[/bold blue]")
        
        async def fetch_initial_listings():
            stubhub_service = StubHubService()
            results = await stubhub_service.fetch_all_events_listings(events)
            
            total_listings = sum(results.values())
            events_with_listings = sum(1 for count in results.values() if count > 0)
            
            console.print(f"[bold green]Initial fetch complete: Found listings for "
                         f"{events_with_listings}/{len(events)} events, "
                         f"Stored {total_listings} total listings[/bold green]")
        
        asyncio.run(fetch_initial_listings())
        
        # Start scheduler
        console.print("\n[bold blue]Step 4: Starting scheduler...[/bold blue]")
        interval = settings.base_scrape_interval_hours
        randomization = "poisson"  # Best for avoiding detection
        
        console.print(f"Using base interval of [yellow]{interval} hours[/yellow] "
                     f"with [yellow]{randomization}[/yellow] randomization")
        
        # Define the job function
        async def fetch_all_listings_job():
            try:
                events = EventRepository.get_all()
                stubhub_service = StubHubService()
                results = await stubhub_service.fetch_all_events_listings(events)
                
                total_listings = sum(results.values())
                events_with_listings = sum(1 for count in results.values() if count > 0)
                
                logger.info(
                    f"Scheduled job completed: Found listings for {events_with_listings}/{len(events)} events, "
                    f"Stored {total_listings} total listings"
                )
                
                return results
            except Exception as e:
                logger.error(f"Error in scheduled job: {e}")
                return None
        
        # Create a wrapper to run the async job
        def run_listings_job():
            return asyncio.run(fetch_all_listings_job())
        
        # Add the job to the scheduler
        job_manager.add_job(
            name="fetch_listings",
            func=run_listings_job,
            interval_hours=interval,
            randomization_strategy=randomization
        )
        
        # Start the job manager
        job_manager.start()
        
        # Show job schedule
        job_manager.print_status()
        
        console.print(
            f"\n[bold green]Ticket Tracker is running![/bold green]\n"
            f"Press Ctrl+C to stop...\n"
        )
        
        # Keep the main thread running
        try:
            while True:
                time.sleep(10)
                # Update status every minute
                if int(time.time()) % 60 < 10:
                    job_manager.print_status()
        except KeyboardInterrupt:
            console.print("\n[bold yellow]Stopping Ticket Tracker...[/bold yellow]")
            job_manager.stop()
            console.print("[bold green]Ticket Tracker stopped[/bold green]")
    
    except Exception as e:
        console.print(f"[bold red]Error running Ticket Tracker: {e}[/bold red]")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()

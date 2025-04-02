# Secondary Ticket Data Tracking Project - Enhanced Architecture

## Project Overview
This project captures secondary ticket market data for live events by:
1. Reading event data from a Google Spreadsheet
2. Fetching ticket listings from StubHub API for tracked events
3. Storing time-series data in TimescaleDB for analysis
4. Using intelligent randomization to avoid detection

## Enhanced Architecture Design

### Core Principles
- **Maintainability**: Clean architecture with separation of concerns
- **Scalability**: Design patterns that allow for future growth
- **Resilience**: Robust error handling and recovery mechanisms
- **Observability**: Comprehensive logging and monitoring

### Improved Tech Stack
- **Language**: Python 3.9+
- **Database**: TimescaleDB (Cloud Instance)
- **Key Dependencies**:
  - `gspread` - Google Sheets integration
  - `requests` - API client with retry capabilities
  - `psycopg2-binary` - PostgreSQL connection
  - `python-dotenv` - Environment management
  - `pydantic` - Data validation and settings management
  - `rich` - Beautiful and informative console output
  - `structlog` - Structured logging
  - `schedule` - Task scheduling
  - `typer` - Command-line interface
  - `tenacity` - Retry logic
  - `pandas` - Data manipulation

## Clean Architecture Implementation

### Directory Structure

```
ticket-tracker/
├── .env.example               # Template for environment variables
├── .gitignore                 # Git ignore file
├── README.md                  # Project documentation
├── pyproject.toml             # Modern Python project configuration
├── requirements.txt           # Project dependencies
├── src/                       # All source code lives here
│   ├── __init__.py
│   ├── config/                # Application configuration
│   │   ├── __init__.py
│   │   └── settings.py        # Pydantic settings model
│   ├── core/                  # Core application logic
│   │   ├── __init__.py 
│   │   ├── db.py              # Database connection management
│   │   └── logging.py         # Logging configuration
│   ├── data/                  # Data operations
│   │   ├── __init__.py
│   │   ├── google_sheets.py   # Google Sheets client
│   │   └── stubhub.py         # StubHub API client
│   ├── domain/                # Business domain models
│   │   ├── __init__.py
│   │   ├── event.py           # Event model
│   │   └── listing.py         # Listing model
│   ├── infrastructure/        # External service adapters
│   │   ├── __init__.py
│   │   ├── database/          # Database operations
│   │   │   ├── __init__.py
│   │   │   ├── event_repo.py  # Event repository
│   │   │   └── listing_repo.py # Listing repository
│   │   └── services/          # External service clients
│   │       ├── __init__.py
│   │       ├── google_api.py  # Google API client
│   │       └── stubhub_api.py # StubHub API client
│   ├── scheduler/             # Scheduling logic
│   │   ├── __init__.py
│   │   ├── job_manager.py     # Job management
│   │   └── randomizer.py      # Randomization strategies
│   └── utils/                 # Utilities
│       ├── __init__.py
│       ├── concurrency.py     # Threading/async utilities
│       └── retry.py           # Retry decorators
└── cli.py                     # Command-line entry point
```

## Robust Logging Implementation with Rich

Rich provides beautiful terminal output with syntax highlighting, tables, progress bars, and more. Combined with structlog for structured logging, we'll create a powerful observability solution.

### Logging Configuration

```python
# src/core/logging.py
import os
import sys
import logging
import structlog
from rich.console import Console
from rich.logging import RichHandler
from rich.traceback import install as install_rich_traceback
from datetime import datetime

from ..config.settings import settings

# Install rich traceback handler for beautiful exception formatting
install_rich_traceback(show_locals=True)

# Create console for rich output
console = Console()

def configure_logging():
    """Configure structured logging with Rich for console and file output."""
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    
    # Configure rich handler for console output
    rich_handler = RichHandler(
        console=console,
        rich_tracebacks=True, 
        tracebacks_show_locals=True,
        markup=True,
        show_time=False,  # structlog will add this
    )
    
    # Configure file handler for persistent logs
    timestamp = datetime.now().strftime("%Y%m%d")
    file_handler = logging.FileHandler(f"logs/ticket_tracker_{timestamp}.log")
    
    # Basic logging configuration
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(message)s",
        datefmt="[%X]",
        handlers=[rich_handler, file_handler]
    )
    
    # Define processors for structlog
    processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
        structlog.contextvars.merge_contextvars,
        structlog.processors.dict_tracebacks,
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ]
    
    # Configure structlog to work with standard library logging
    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Create formatter for file handler
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(sort_keys=True)
        ],
    )
    file_handler.setFormatter(formatter)
    
    # Return a configured logger
    return structlog.get_logger()

def get_logger(name: str = None):
    """Get a configured logger instance."""
    return structlog.get_logger(name)
```

### Example Usage in Application

```python
# src/data/stubhub.py
from ..core.logging import get_logger
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.panel import Panel
from rich.console import Console
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import requests

console = Console()
logger = get_logger(__name__)

class StubHubClient:
    """Client for interacting with the StubHub API."""
    
    def __init__(self, base_url):
        self.base_url = base_url
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(requests.exceptions.RequestException),
        before_sleep=lambda retry_state: logger.info(
            "Retry attempt",
            attempt=retry_state.attempt_number,
            wait=retry_state.next_action.sleep
        )
    )
    async def get_listings(self, viagogo_id):
        """Get ticket listings for an event."""
        url = f"{self.base_url}?viagogoEventId={viagogo_id}"
        
        logger.info("Fetching ticket listings", viagogo_id=viagogo_id)
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]Fetching listings for {task.fields[event_id]}..."),
            TimeElapsedColumn(),
            console=console,
            transient=True
        ) as progress:
            task = progress.add_task("Fetch", event_id=viagogo_id)
            
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                progress.update(task, completed=True)
                
                logger.info(
                    "Successfully fetched listings",
                    viagogo_id=viagogo_id,
                    count=len(data)
                )
                
                console.print(Panel.fit(
                    f"[green]✓[/green] Fetched [bold]{len(data)}[/bold] listings for event [bold]{viagogo_id}[/bold]",
                    title="StubHub API"
                ))
                
                return data
                
            except requests.exceptions.RequestException as e:
                logger.error(
                    "Failed to fetch listings",
                    viagogo_id=viagogo_id,
                    error=str(e),
                    exc_info=True
                )
                
                console.print(Panel.fit(
                    f"[red]✗[/red] Error fetching listings for event [bold]{viagogo_id}[/bold]: {str(e)}",
                    title="StubHub API Error"
                ))
                
                raise
```

## Enhanced Settings Management with Pydantic

Pydantic provides data validation and settings management with environment variable loading built-in.

```python
# src/config/settings.py
from pydantic import BaseSettings, Field, PostgresDsn, validator
from typing import Optional, Dict, Any
import os

class Settings(BaseSettings):
    """Application settings with validation."""
    
    # Project info
    project_name: str = "Ticket Tracker"
    version: str = "1.0.0"
    
    # Google Sheets
    google_sheet_id: str = Field(..., env="GOOGLE_SHEET_ID")
    google_creds_file: str = Field(..., env="GOOGLE_CREDS_FILE")
    events_worksheet_name: str = "Events"
    
    # StubHub API
    stubhub_api_base_url: str = "https://pro.stubhub.com/api/Listing/GetCompListingsByEventId"
    
    # Database
    db_host: str = Field(..., env="DB_HOST")
    db_port: str = Field(..., env="DB_PORT")
    db_name: str = Field(..., env="DB_NAME")
    db_user: str = Field(..., env="DB_USER")
    db_password: str = Field(..., env="DB_PASSWORD", repr=False)  # Hide in logs
    db_connection_string: Optional[PostgresDsn] = None
    
    @validator("db_connection_string", pre=True)
    def assemble_db_connection(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v
        return PostgresDsn.build(
            scheme="postgresql",
            user=values.get("db_user"),
            password=values.get("db_password"),
            host=values.get("db_host"),
            port=values.get("db_port"),
            path=f"/{values.get('db_name') or ''}",
        )
    
    # Scraping settings
    base_scrape_interval_hours: int = Field(4, env="BASE_SCRAPE_INTERVAL_HOURS")
    randomization_factor: float = 0.25
    min_request_delay: int = 2
    max_request_delay: int = 5
    
    # Logging
    log_level: str = Field("INFO", env="LOG_LEVEL")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Create a global settings instance
settings = Settings()
```

## Database Connection Management

Efficient connection pooling and context management:

```python
# src/core/db.py
import contextlib
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor
from ..config.settings import settings
from ..core.logging import get_logger

logger = get_logger(__name__)

# Global connection pool
pool = None

def setup_connection_pool():
    """Initialize the database connection pool."""
    global pool
    
    if pool is not None:
        return
    
    try:
        pool = ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            host=settings.db_host,
            port=settings.db_port,
            dbname=settings.db_name,
            user=settings.db_user,
            password=settings.db_password,
            cursor_factory=RealDictCursor,
        )
        logger.info("Database connection pool initialized")
    except Exception as e:
        logger.error("Failed to initialize database connection pool", error=str(e))
        raise

@contextlib.contextmanager
def get_db_connection():
    """Get a database connection from the pool with context management."""
    global pool
    
    if pool is None:
        setup_connection_pool()
    
    conn = None
    try:
        conn = pool.getconn()
        logger.debug("Acquired database connection from pool")
        yield conn
    except Exception as e:
        logger.error("Database connection error", error=str(e))
        raise
    finally:
        if conn is not None:
            pool.putconn(conn)
            logger.debug("Released database connection back to pool")

@contextlib.contextmanager
def get_db_cursor(commit=False):
    """Get a database cursor with automatic connection management."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            yield cursor
            if commit:
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
```

## Pydantic Domain Models

Type safety and validation with Pydantic models:

```python
# src/domain/event.py
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class Event(BaseModel):
    """Domain model for events."""
    event_id: Optional[int] = None
    event_name: str
    venue: str
    city: str
    country: str
    event_date: datetime
    viagogo_id: str
    is_tracked: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        orm_mode = True

# src/domain/listing.py
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class PriceInfo(BaseModel):
    """Price information model."""
    amt: float
    disp: str
    currency: str
    dec: int

class Listing(BaseModel):
    """Domain model for ticket listings."""
    listing_id: int
    event_id: Optional[int] = None
    section: str
    row: str
    available_tickets: int
    seller_net_proceeds: PriceInfo
    seller_all_in_price: PriceInfo
    currency_code: str
    timestamp: Optional[datetime] = None
    
    class Config:
        orm_mode = True
```

## Repository Pattern Implementation

Separation of data access from business logic:

```python
# src/infrastructure/database/event_repo.py
from typing import List, Optional
from ...domain.event import Event
from ...core.db import get_db_cursor
from ...core.logging import get_logger

logger = get_logger(__name__)

class EventRepository:
    """Repository for event data operations."""
    
    @staticmethod
    async def get_all_active() -> List[Event]:
        """Get all active events that should be tracked."""
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM events 
                WHERE is_tracked = TRUE AND event_date > NOW()
                ORDER BY event_date
            """)
            
            rows = cursor.fetchall()
            logger.info(f"Retrieved {len(rows)} active events")
            
            return [Event.parse_obj(row) for row in rows]
    
    @staticmethod
    async def upsert_from_spreadsheet(events: List[Event]) -> int:
        """Update or insert events from spreadsheet data."""
        count = 0
        with get_db_cursor(commit=True) as cursor:
            for event in events:
                cursor.execute("""
                    INSERT INTO events 
                    (event_name, venue, city, country, event_date, viagogo_id, is_tracked)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (viagogo_id)
                    DO UPDATE SET
                        event_name = EXCLUDED.event_name,
                        venue = EXCLUDED.venue,
                        city = EXCLUDED.city,
                        country = EXCLUDED.country,
                        event_date = EXCLUDED.event_date,
                        is_tracked = EXCLUDED.is_tracked,
                        updated_at = NOW()
                    RETURNING event_id
                """, (
                    event.event_name,
                    event.venue,
                    event.city,
                    event.country,
                    event.event_date,
                    event.viagogo_id,
                    event.is_tracked
                ))
                count += 1
            
            logger.info(f"Upserted {count} events from spreadsheet")
            return count
```

## Command-Line Interface with Typer

Create a powerful CLI with minimal code:

```python
# cli.py
import typer
from rich.console import Console
import asyncio
import time
from src.core.logging import configure_logging, console
from src.data.google_sheets import update_events_from_spreadsheet
from src.scheduler.job_manager import start_scheduler
from src.config.settings import settings

app = typer.Typer(help="Secondary Ticket Data Tracking System")
logger = configure_logging()

@app.command()
def init_db():
    """Initialize the database schema."""
    from src.infrastructure.database.setup import setup_database
    
    console.print("[bold blue]Initializing database schema...[/bold blue]")
    setup_database()
    console.print("[bold green]Database schema initialized successfully![/bold green]")

@app.command()
def sync_events():
    """Sync events from Google Spreadsheet to database."""
    console.print("[bold blue]Syncing events from Google Spreadsheet...[/bold blue]")
    asyncio.run(update_events_from_spreadsheet())
    console.print("[bold green]Events synced successfully![/bold green]")

@app.command()
def scrape(event_id: str = typer.Option(None, help="Specific viagogo event ID to scrape")):
    """Run a scraping job for all events or a specific event."""
    from src.data.stubhub import scrape_all_events, scrape_event
    
    if event_id:
        console.print(f"[bold blue]Scraping data for event {event_id}...[/bold blue]")
        asyncio.run(scrape_event(event_id))
    else:
        console.print("[bold blue]Scraping data for all active events...[/bold blue]")
        asyncio.run(scrape_all_events())
    console.print("[bold green]Scraping completed successfully![/bold green]")

@app.command()
def run():
    """Start the ticket tracking system."""
    console.print(f"[bold blue]Starting {settings.project_name} v{settings.version}[/bold blue]")
    
    try:
        # Initialize database
        from src.infrastructure.database.setup import setup_database
        setup_database()
        
        # Sync events from spreadsheet
        asyncio.run(update_events_from_spreadsheet())
        
        # Start the scheduler
        start_scheduler()
        
        # Keep the main thread alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            console.print("[yellow]Shutting down...[/yellow]")
            
    except Exception as e:
        logger.exception("Application error")
        console.print(f"[bold red]Error: {str(e)}[/bold red]")
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()
```

## Dockerization for Production

```dockerfile
# Dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc python3-dev libpq-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1

# Run the application
CMD ["python", "cli.py", "run"]
```

## Docker Compose for Development

```yaml
# docker-compose.yml
version: '3.8'

services:
  app:
    build: .
    volumes:
      - .:/app
    env_file:
      - .env
    ports:
      - "8000:8000"
    command: python cli.py run
    depends_on:
      - redis
    restart: unless-stopped

  redis:
    image: redis:alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped

volumes:
  redis_data:
```

## Improved Randomization Strategy

Implement a more sophisticated randomization strategy to make scraping patterns less predictable:

```python
# src/scheduler/randomizer.py
import random
import time
from datetime import datetime, timedelta
import math
from ..core.logging import get_logger

logger = get_logger(__name__)

class RandomizationStrategy:
    """Implements various randomization strategies for scraping."""
    
    @staticmethod
    def poisson_interval(mean_interval):
        """Use a Poisson process to determine the next interval.
        
        This creates a more natural random pattern than uniform distribution.
        """
        # Poisson process: -ln(1-random) * mean
        return -math.log(1.0 - random.random()) * mean_interval
    
    @staticmethod
    def get_next_run_time(base_hours, randomization_factor=0.25, min_factor=0.5):
        """Get next run time with sophisticated randomization.
        
        Args:
            base_hours: Base interval in hours
            randomization_factor: How much randomization to apply (0-1)
            min_factor: Minimum fraction of base interval allowed
        
        Returns:
            datetime: Next run time
        """
        base_seconds = base_hours * 3600
        
        # Use Poisson process for more natural randomization
        adjusted_seconds = RandomizationStrategy.poisson_interval(base_seconds)
        
        # Apply bounds
        min_seconds = base_seconds * min_factor
        adjusted_seconds = max(adjusted_seconds, min_seconds)
        
        next_run = datetime.now() + timedelta(seconds=adjusted_seconds)
        
        logger.info(
            "Calculated next run time",
            base_hours=base_hours,
            adjusted_seconds=adjusted_seconds,
            next_run=next_run.isoformat()
        )
        
        return next_run
    
    @staticmethod
    def get_request_delay(min_delay, max_delay, bias='normal'):
        """Get a randomized delay between API requests.
        
        Args:
            min_delay: Minimum delay in seconds
            max_delay: Maximum delay in seconds
            bias: Distribution bias ('uniform', 'normal', or 'exponential')
            
        Returns:
            float: Delay in seconds
        """
        if bias == 'uniform':
            # Simple uniform distribution
            return random.uniform(min_delay, max_delay)
        
        elif bias == 'normal':
            # Normal distribution centered between min and max
            mean = (min_delay + max_delay) / 2
            std_dev = (max_delay - min_delay) / 6  # 99.7% within range
            while True:
                delay = random.normalvariate(mean, std_dev)
                if min_delay <= delay <= max_delay:
                    return delay
        
        elif bias == 'exponential':
            # Exponential distribution - more shorter delays, fewer longer ones
            scale = (max_delay - min_delay) / 3
            while True:
                delay = min_delay + random.expovariate(1.0 / scale)
                if delay <= max_delay:
                    return delay
        
        else:
            return random.uniform(min_delay, max_delay)

    @staticmethod
    def apply_jitter(seconds, jitter_factor=0.1):
        """Apply a small random jitter to a time value."""
        jitter = seconds * jitter_factor * (random.random() * 2 - 1)
        return max(0, seconds + jitter)
```

## Efficient Batch Processing

Improve performance when dealing with large datasets:

```python
# src/infrastructure/database/listing_repo.py
from typing import List
import psycopg2.extras
from datetime import datetime
from ...domain.listing import Listing
from ...core.db import get_db_connection
from ...core.logging import get_logger

logger = get_logger(__name__)

class ListingRepository:
    """Repository for ticket listing data operations."""
    
    @staticmethod
    async def batch_insert(event_id: int, listings: List[dict]) -> int:
        """Insert multiple listings in an efficient batch operation."""
        if not listings:
            return 0
            
        timestamp = datetime.now()
        count = 0
        
        with get_db_connection() as conn:
            # Convert to parameter list for executemany
            batch_data = []
            for listing in listings:
                try:
                    batch_data.append((
                        listing['listingId'],
                        event_id,
                        listing.get('section', ''),
                        listing.get('row', ''),
                        listing.get('availableTickets', 0),
                        listing['sellerNetProceeds']['amt'],
                        listing['sellerAllInPrice']['amt'],
                        listing['currencyCode'],
                        timestamp
                    ))
                except (KeyError, TypeError) as e:
                    logger.warning(
                        "Skipping invalid listing", 
                        listing_id=listing.get('listingId', 'unknown'),
                        error=str(e)
                    )
            
            if not batch_data:
                return 0
                
            # Use efficient batch insert
            cursor = conn.cursor()
            try:
                psycopg2.extras.execute_batch(
                    cursor,
                    """
                    INSERT INTO listings
                    (listing_id, event_id, section, row, available_tickets,
                     seller_net_proceeds, seller_all_in_price, currency_code, timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    batch_data,
                    page_size=100  # Process in chunks of 100
                )
                conn.commit()
                count = len(batch_data)
                
                logger.info(
                    "Batch inserted listings",
                    event_id=event_id,
                    count=count
                )
                
            except Exception as e:
                conn.rollback()
                logger.error(
                    "Error in batch insert",
                    event_id=event_id,
                    error=str(e),
                    exc_info=True
                )
                raise
            finally:
                cursor.close()
                
        return count
```

## Data Transfer Objects (DTOs)

Create DTO classes to transform between different layers:

```python
# src/domain/dto.py
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime

class SpreadsheetEventDTO(BaseModel):
    """Data transfer object for events from spreadsheet."""
    event_name: str
    venue: str
    city: str
    country: str
    event_date: datetime
    viagogo_id: str
    is_tracked: bool
    
    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> 'SpreadsheetEventDTO':
        """Convert a spreadsheet row to DTO object."""
        return cls(
            event_name=row.get('Event Name', ''),
            venue=row.get('Venue', ''),
            city=row.get('City', ''),
            country=row.get('Country', ''),
            event_date=datetime.strptime(
                row.get('Event Date (Local)', ''), 
                '%Y-%m-%d %H:%M:%S'
            ),
            viagogo_id=str(row.get('viagId', '')),
            is_tracked=row.get('is_tracked', 'FALSE').upper() == 'TRUE'
        )

class TicketStatsDTO(BaseModel):
    """Statistics for ticket listings."""
    event_id: int
    event_name: str
    min_price: float
    max_price: float
    avg_price: float
    total_listings: int
    total_tickets: int
    timestamp: datetime
```

## Modern Python Project Configuration

Using `pyproject.toml` for modern Python project configuration:

```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=42", "wheel"]
build-backend = "setuptools.build_meta"

[tool.black]
line-length = 88
target-version = ['py39']
include = '\.pyi?

Create a beautiful console dashboard to monitor the application:

```python
# src/core/dashboard.py
import threading
import time
from datetime import datetime
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich import box
from ..config.settings import settings
from ..infrastructure.database.stats_repo import StatsRepository

console = Console()

def generate_dashboard():
    """Generate a rich dashboard layout."""
    layout = Layout()
    
    layout.split(
        Layout(name="header", size=3),
        Layout(name="main")
    )
    
    layout["main"].split_row(
        Layout(name="events", ratio=2),
        Layout(name="stats", ratio=3)
    )
    
    # Header
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = Panel(
        f"[bold][blue]{settings.project_name}[/blue] v{settings.version}[/bold] | Running since {start_time} | Current time: {now}",
        box=box.ROUNDED
    )
    layout["header"].update(header)
    
    # Events table
    events_table = Table(
        title="Active Events", 
        box=box.SIMPLE,
        show_header=True,
        header_style="bold magenta"
    )
    events_table.add_column("Event")
    events_table.add_column("Date", style="cyan")
    events_table.add_column("ID", style="dim")
    
    for event in recent_events:
        events_table.add_row(
            f"{event.event_name} - {event.city}",
            event.event_date.strftime("%Y-%m-%d"),
            event.viagogo_id
        )
    
    events_panel = Panel(
        events_table,
        title="[bold]Active Events[/bold]",
        border_style="blue",
        box=box.ROUNDED
    )
    layout["events"].update(events_panel)
    
    # Stats
    stats_table = Table(
        title="Recent Scrape Stats",
        box=box.SIMPLE,
        show_header=True,
        header_style="bold cyan"
    )
    
    stats_table.add_column("Event")
    stats_table.add_column("Last Scraped", style="cyan")
    stats_table.add_column("Listings", justify="right")
    stats_table.add_column("Avg Price", justify="right", style="green")
    
    for stat in recent_stats:
        stats_table.add_row(
            stat.event_name,
            stat.timestamp.strftime("%H:%M:%S"),
            str(stat.total_listings),
            f"${stat.avg_price:.2f}"
        )
    
    stats_panel = Panel(
        stats_table,
        title="[bold]Recent Scraping Activity[/bold]",
        border_style="blue",
        box=box.ROUNDED
    )
    layout["stats"].update(stats_panel)
    
    return layout

# Global variables for dashboard
start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
recent_events = []
recent_stats = []

def update_dashboard_data():
    """Background thread to update dashboard data."""
    global recent_events, recent_stats
    
    while True:
        try:
            # Update events list
            from ..infrastructure.database.event_repo import EventRepository
            recent_events = asyncio.run(EventRepository.get_all_active())
            
            # Update stats
            recent_stats = asyncio.run(StatsRepository.get_recent_stats(limit=10))
            
            time.sleep(30)  # Update every 30 seconds
        except Exception as e:
            print(f"Error updating dashboard: {str(e)}")
            time.sleep(60)  # Wait longer before retry

def start_dashboard():
    """Start the rich dashboard."""
    # Start background data update thread
    threading.Thread(target=update_dashboard_data, daemon=True).start()
    
    with Live(generate_dashboard(), refresh_per_second=1) as live:
        while True:
            live.update(generate_dashboard())
            time.sleep(1)

[tool.isort]
profile = "black"
multi_line_output = 3

[tool.pytest.ini_options]
minversion = "6.0"
testpaths = ["tests"]
python_files = "test_*.py"

[tool.mypy]
python_version = "3.9"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true

[project]
name = "ticket-tracker"
version = "1.0.0"
description = "Secondary Ticket Data Tracking System"
readme = "README.md"
requires-python = ">=3.9"
license = {text = "MIT"}
authors = [
    {name = "Your Name", email = "your.email@example.com"}
]
dependencies = [
    "gspread>=5.0.0",
    "requests>=2.28.1",
    "psycopg2-binary>=2.9.3",
    "python-dotenv>=0.21.0",
    "pydantic>=1.10.2",
    "rich>=12.6.0",
    "structlog>=22.1.0",
    "schedule>=1.1.0",
    "typer>=0.7.0",
    "tenacity>=8.1.0",
    "pandas>=1.5.1",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "black>=22.10.0",
    "isort>=5.10.1",
    "mypy>=0.991",
    "flake8>=5.0.4",
    "pre-commit>=2.20.0",
]

[project.scripts]
ticket-tracker = "cli:app"
```

## Asyncio for Efficient IO Operations

Leverage Python's asyncio for concurrent operations:

```python
# src/data/stubhub.py
import asyncio
import aiohttp
from typing import List, Dict, Any, Optional
import random
from ..core.logging import get_logger
from ..config.settings import settings
from ..domain.listing import Listing
from ..infrastructure.database.listing_repo import ListingRepository
from ..scheduler.randomizer import RandomizationStrategy

logger = get_logger(__name__)

async def fetch_ticket_listings(session: aiohttp.ClientSession, viagogo_id: str) -> Optional[List[Dict[str, Any]]]:
    """Fetch ticket listings for an event using aiohttp."""
    url = f"{settings.stubhub_api_base_url}?viagogoEventId={viagogo_id}"
    
    try:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                logger.info(f"Fetched {len(data)} listings for event {viagogo_id}")
                return data
            else:
                logger.error(f"Error fetching listings for event {viagogo_id}: HTTP {response.status}")
                return None
    except Exception as e:
        logger.error(f"Exception fetching listings for event {viagogo_id}: {str(e)}")
        return None

async def scrape_event(event_id: int, viagogo_id: str) -> int:
    """Scrape ticket data for a specific event."""
    async with aiohttp.ClientSession() as session:
        listings = await fetch_ticket_listings(session, viagogo_id)
        
        if not listings:
            return 0
            
        count = await ListingRepository.batch_insert(event_id, listings)
        logger.info(f"Stored {count} listings for event {viagogo_id}")
        return count

async def scrape_all_events() -> Dict[int, int]:
    """Scrape ticket data for all active events with controlled concurrency."""
    from ..infrastructure.database.event_repo import EventRepository
    
    events = await EventRepository.get_all_active()
    logger.info(f"Starting scrape cycle for {len(events)} events")
    
    results = {}
    
    # Use a semaphore to limit concurrent requests
    semaphore = asyncio.Semaphore(3)  # Max 3 concurrent requests
    
    async def scrape_with_delay(event):
        async with semaphore:
            count = await scrape_event(event.event_id, event.viagogo_id)
            results[event.event_id] = count
            
            # Random delay between requests to avoid detection
            delay = RandomizationStrategy.get_request_delay(
                settings.min_request_delay,
                settings.max_request_delay,
                bias='normal'
            )
            await asyncio.sleep(delay)
    
    # Create tasks for each event
    tasks = [scrape_with_delay(event) for event in events]
    
    # Run all tasks concurrently (with controlled concurrency via semaphore)
    await asyncio.gather(*tasks)
    
    logger.info(f"Completed scrape cycle. Scraped {sum(results.values())} listings across {len(results)} events")
    return results
```

## Main Application With Rich Console Dashboard

Create a beautiful console dashboard to monitor the application:

```python
# src/core/dashboard.py
import threading
import time
from datetime import datetime
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich import box
from ..config.settings import settings
from ..infrastructure.database.stats_repo import StatsRepository

console = Console()

def generate_dashboard():
    """Generate a rich dashboard layout."""
    layout = Layout()
    
    layout.split(
        Layout(name="header", size=3),
        Layout(name="main")
    )
    
    layout["main"].split_row(
        Layout(name="events", ratio=2),
        Layout(name="stats", ratio=3)
    )
    
    # Header
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = Panel(
        f"[bold][blue]{settings.project_name}[/blue] v{settings.version}[/bold] | Running since {start_time} | Current time: {now}",
        box=box.ROUNDED
    )
    layout["header"].update(header)
    
    # Events table
    events_table = Table(
        title="Active Events", 
        box=box.SIMPLE,
        show_header=True,
        header_style="bold magenta"
    )
    events_table.add_column("Event")
    events_table.add_column("Date", style="cyan")
    events_table.add_column("ID", style="dim")
    
    for event in recent_events:
        events_table.add_row(
            f"{event.event_name} - {event.city}",
            event.event_date.strftime("%Y-%m-%d"),
            event.viagogo_id
        )
    
    events_panel = Panel(
        events_table,
        title="[bold]Active Events[/bold]",
        border_style="blue",
        box=box.ROUNDED
    )
    layout["events"].update(events_panel)
    
    # Stats
    stats_table = Table(
        title="Recent Scrape Stats",
        box=box.SIMPLE,
        show_header=True,
        header_style="bold cyan"
    )
    
    stats_table.add_column("Event")
    stats_table.add_column("Last Scraped", style="cyan")
    stats_table.add_column("Listings", justify="right")
    stats_table.add_column("Avg Price", justify="right", style="green")
    
    for stat in recent_stats:
        stats_table.add_row(
            stat.event_name,
            stat.timestamp.strftime("%H:%M:%S"),
            str(stat.total_listings),
            f"${stat.avg_price:.2f}"
        )
    
    stats_panel = Panel(
        stats_table,
        title="[bold]Recent Scraping Activity[/bold]",
        border_style="blue",
        box=box.ROUNDED
    )
    layout["stats"].update(stats_panel)
    
    return layout

# Global variables for dashboard
start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
recent_events = []
recent_stats = []

def update_dashboard_data():
    """Background thread to update dashboard data."""
    global recent_events, recent_stats
    
    while True:
        try:
            # Update events list
            from ..infrastructure.database.event_repo import EventRepository
            recent_events = asyncio.run(EventRepository.get_all_active())
            
            # Update stats
            recent_stats = asyncio.run(StatsRepository.get_recent_stats(limit=10))
            
            time.sleep(30)  # Update every 30 seconds
        except Exception as e:
            print(f"Error updating dashboard: {str(e)}")
            time.sleep(60)  # Wait longer before retry

def start_dashboard():
    """Start the rich dashboard."""
    # Start background data update thread
    threading.Thread(target=update_dashboard_data, daemon=True).start()
    
    with Live(generate_dashboard(), refresh_per_second=1) as live:
        while True:
            live.update(generate_dashboard())
            time.sleep(1)
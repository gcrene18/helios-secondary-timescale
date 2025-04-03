# Secondary Ticket Market Data Tracker

A robust system for tracking ticket price data from secondary markets using a clean architecture approach with TimescaleDB for time-series data storage.

## Overview

This application collects and analyzes ticket listing data from secondary markets like StubHub for live events. It fetches event information from Google Sheets and retrieves ticket listings via API, storing the time-series data in TimescaleDB for analysis.

## Features

- **Clean Architecture**: Organized with clear separation of concerns (domain, data, infrastructure, services)
- **Event Management**: Fetch event data from Google Sheets and store in TimescaleDB
- **Ticket Tracking**: Retrieve ticket listings and pricing data from StubHub API
- **Time-Series Data**: Store historical pricing data with TimescaleDB
- **Randomized Scheduling**: Intelligent job scheduling with randomization to avoid detection
- **Observability**: Comprehensive structured logging with Rich and structlog
- **Resilience**: Retry mechanisms and error handling for API calls
- **CLI Interface**: User-friendly command-line interface for all operations

## Architecture

```
src/
├── config/            # Application configuration
├── core/              # Core components (logging, database)
├── data/              # External data access clients
├── domain/            # Domain models and business rules
├── infrastructure/    # Implementation details
│   ├── database/      # Database repositories
│   └── services/      # Service implementations
├── scheduler/         # Scheduling and randomization
└── utils/             # Utility functions
```

## Requirements

- Python 3.8+
- PostgreSQL with TimescaleDB extension
- Google Sheets API credentials

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd helios-secondary-timescale
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Set up environment variables by creating a `.env` file:
   ```
   # Database
   DB_HOST=localhost
   DB_PORT=5432
   DB_NAME=ticket_tracker
   DB_USER=your_username
   DB_PASSWORD=your_password
   DB_SCHEMA=public
   
   # Google Sheets
   GOOGLE_SHEET_ID=your_sheet_id
   GOOGLE_SHEETS_CREDENTIALS_FILE=credentials.json
   EVENTS_WORKSHEET_NAME=Events
   
   # Scraping Settings
   BASE_SCRAPE_INTERVAL_HOURS=12.0
   STUBHUB_API_BASE_URL=https://stubhub.com/api/events
   
   # Randomization Settings
   MIN_RANDOM_FACTOR=0.7
   MAX_RANDOM_FACTOR=1.3
   DEFAULT_RANDOMIZATION_STRATEGY=poisson
   ```

4. Place your Google Sheets API credentials in `credentials.json`

## Usage

The application provides a command-line interface with several commands:

### Initialize the Database

```bash
python cli.py init-db
```

### Manage Events

```bash
# Fetch events from Google Sheets
python cli.py fetch-events

# Show all events in the database
python cli.py show-events
```

### Cleanup Untracked Events

# Event Tracking Management

Events in the tracking system can be marked as "tracked" or "untracked" in your Google Sheet. Only tracked events will be imported into the database during the initial fetch. The system respects the `is_tracked` column (7th column) in your Google Sheets data.

## Managing Tracked Events

```bash
# Fetch events from Google Sheet (only imports events marked as tracked)
python cli.py fetch-events

# Cleanup events that are no longer tracked
python cli.py cleanup-untracked-events  # Dry run by default, shows what would be affected

# Mark untracked events in the database (keeps the data but skips future updates)
python cli.py cleanup-untracked-events --no-dry-run

# Delete untracked events entirely from the database
python cli.py cleanup-untracked-events --no-dry-run --delete

### Manage Listings

```bash
# Fetch ticket listings for all events
python cli.py fetch-listings

# Fetch listings for a specific event
python cli.py fetch-listings <viagogo_id>

# Show listings for a specific event
python cli.py show-listings <event_id>
```

### Analytics

```bash
# View price history for an event
python cli.py price-history <event_id> --days 30 --bucket "1 day"

# View prices by section for an event
python cli.py section-prices <event_id> --days 7
```

### Scheduler

```bash
# Start the scheduler with default settings
python cli.py start-scheduler

# Start with custom interval and randomization
python cli.py start-scheduler --interval-hours 6 --randomization poisson
```

### Run the Full System

```bash
# Run the complete system (initializes database, fetches events, and starts scheduler)
python cli.py run
```

## Randomization Strategies

The system supports different randomization strategies to avoid detection during scraping:

- **Uniform**: Simple random distribution between min and max factors
- **Poisson**: Natural-looking timing patterns (recommended for avoiding detection)
- **Normal**: Gaussian distribution around the mean interval

## Database Schema

### Events Table

- `event_id`: Primary key
- `viagogo_id`: External ID from the ticket provider
- `name`: Event name
- `venue`: Venue name
- `city`: City where the event is held
- `country`: Country where the event is held
- `event_date`: Date and time of the event
- `created_at`: When the record was created
- `updated_at`: When the record was last updated

### Listings Table (TimescaleDB Hypertable)

- `listing_id`: Primary key
- `event_id`: Foreign key to events table
- `section`: Section in the venue
- `row`: Row in the section
- `quantity`: Number of tickets
- `price_per_ticket`: Price per ticket
- `total_price`: Total price for all tickets
- `currency`: Currency code
- `captured_at`: When the listing was observed (time dimension)

## Development

### Adding New Events

Add events to your Google Sheet with the following columns:
- Name
- Venue
- City
- Country
- Date (YYYY-MM-DD HH:MM:SS format)
- viagogoID

### Extending the System

- **New Data Sources**: Add new clients in the `data` directory
- **New Analytics**: Extend repository classes with new query methods
- **Custom Scheduling**: Modify the job manager to support new scheduling patterns

## License

[Specify your license]

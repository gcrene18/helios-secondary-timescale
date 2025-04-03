# StubHub Proxy API Server

This service provides a proxy API for fetching ticket listings from StubHub through browser automation. The system is designed to avoid detection by mimicking human browsing patterns.

## Key Features

- **Browser Automation**: Uses Playwright to control browsers with human-like interaction patterns
- **Stealth Techniques**: Implements various techniques to avoid detection as an automated scraper
- **Caching Layer**: Redis-based caching to minimize repeated requests
- **API Authentication**: Simple API key authentication to secure endpoints
- **Docker Support**: Easy deployment with Docker and docker-compose

## Architecture

The system follows a modular architecture:

- **FastAPI Backend**: Handles HTTP requests and responses
- **Browser Pool**: Manages multiple browser instances for efficient parallel requests
- **Cache Layer**: Stores recently fetched data to reduce load on StubHub
- **Session Manager**: Handles browser session health and rotation

## Setup Instructions

### Local Development

1. Clone the repository
2. Create a virtual environment:
   ```bash
   cd server
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Install Playwright browsers:
   ```bash
   playwright install
   playwright install-deps
   ```

5. Create a `.env` file based on `.env.template`:
   ```bash
   cp .env.template .env
   # Edit .env with your configuration
   ```

6. Start Redis (if not using Docker):
   ```bash
   # Install Redis if not available: https://redis.io/download
   redis-server
   ```

7. Run the application:
   ```bash
   uvicorn main:app --reload
   ```

### Docker Deployment

1. Build and run using docker-compose:
   ```bash
   docker-compose up -d
   ```

2. For production, make sure to:
   - Set `DEBUG=False`
   - Configure a strong API key
   - Set appropriate rate limits

## API Endpoints

### Listings

- `GET /listings/{event_id}`: Get ticket listings for a specific StubHub event
  - Query parameters:
    - `force_refresh`: Force a fresh fetch instead of using cache (default: false)

### Health

- `GET /health`: Basic health check
- `GET /health/detailed`: Detailed health status of all components

### Stats

- `GET /stats`: Get usage statistics and metrics

## Configuration Options

See `.env.template` for all available configuration options. Key settings include:

- `API_KEY`: Authentication key for API endpoints
- `MAX_BROWSER_INSTANCES`: Number of parallel browser instances (default: 3)
- `CACHE_TTL_SECONDS`: Cache lifetime for listings (default: 3600 seconds)
- Various stealth settings to control browsing patterns

## Security Considerations

- Set a strong API key in production
- Limit access to the API
- Consider using residential proxies if making frequent requests
- Respect StubHub's terms of service and rate limits

## Maintenance

- Check logs regularly for issues
- Monitor resource usage, especially when running multiple browser instances
- Adjust stealth settings if detection issues occur

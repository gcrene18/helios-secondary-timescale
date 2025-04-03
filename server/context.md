# StubHub Ticket Data Tracking Project: Context Document

## Project Overview

We are building a system to track secondary market ticket prices from StubHub for a list of events. The system needs to be designed with stealth in mind to avoid detection as an automated scraper while collecting data reliably.

## Key Architecture Decisions

### Two-Tier Architecture

The system will use a two-tier architecture:

1. **Proxy API Server**: A separate service that manages browser automation to fetch data from StubHub in a human-like manner.(This is )
2. **Main Application**: Handles data processing, storage, and analysis, communicating with the Proxy API when fresh data is needed.

This separation ensures the sensitive browser automation logic is isolated, making the system more resilient and maintainable.

This directory contains all the data for the Proxy API Server. We will ignore the main application code.

### Browser Automation Approach

Instead of direct API requests which are prone to detection, we will use a full browser automation approach:
- Browsers will navigate to event pages and trigger the natural API requests that occur when viewing listing data
- We'll use real browser fingerprints via GoLogin to avoid detection
- The system will mimic natural human browsing patterns

## Technical Components

### Proxy API Server

- **FastAPI Backend**: Provides a simple API for requesting event data
- **Browser Pool**: Manages multiple parallel browser sessions for efficiency
- **Cache Layer**: Stores recently fetched data to minimize unnecessary browser interactions
- **Session Manager**: Handles browser session health, login state, and rotation

### Browser Automation

- **Playwright**: For browser automation within the proxy server
- **GoLogin Integration**: For managing browser fingerprints to avoid detection
- **Natural Browsing Patterns**: The automation will include natural delays, navigation patterns, and interaction

### Data Management

- **Caching Layer**: To minimize repeated requests for the same event
- **Data Transformation**: Standardize and clean the raw data before storage

## Implementation Guidelines

### Stealth Measures

1. **Natural Browsing Patterns**:
   - Navigate to the event page before accessing listing data
   - Include realistic delays between actions
   - Occasionally perform additional browsing actions
   - Add random mouse movements and clicks

2. **Session Management**:
   - Maintain persistent sessions with proper cookies
   - Keep sessions within natural duration limits (hours, not days)
   - Perform occasional refreshes and natural browsing to maintain session health

3. **Request Patterns**:
   - Limit requests per session to avoid unusual patterns
   - Space requests naturally during business hours
   - Vary the timing between requests

4. **Browser Fingerprinting**:
   - Use GoLogin to manage different browser profiles
   - Rotate profiles periodically
   - Ensure consistent fingerprints within a session

### Proxy API Server Implementation

The server should provide these endpoints:
- `/listing` - Get listing data for a specific event
- `/health` - Check system health
- `/stats` - Get usage statistics

The server should handle:
- Browser session management
- Caching to reduce load
- Error recovery
- Request throttling

### Main Application Implementation

The main application should:
- Manage the event list from Google Sheets
- Schedule data collection with appropriate randomization
- Process and store data in TimescaleDB
- Implement proper error handling and retry logic

## Development Workflow

1. Start by building and testing the proxy API server
2. Implement a simple client to test the proxy
3. Develop the main application with TimescaleDB integration
4. Implement the Google Sheets integration
5. Add monitoring and alerting

## Deployment Considerations

- Deploy the proxy API on servers with residential IPs when possible
- Consider running multiple proxy instances in different locations
- Implement proper monitoring and logging
- Use Docker for consistent deployment

## Ethical and Legal Considerations

- Respect rate limits and terms of service
- Only collect publicly available data
- Do not interfere with normal site operation
- Secure and encrypt any stored authentication credentials

## Security Practices

- Use environment variables for sensitive configuration
- Implement API authentication between your main app and proxy
- Secure all endpoints
- Follow least privilege principles

## Monitoring Requirements

Monitor these key metrics:
- Request success rates
- Browser session health
- Cache hit rates
- Response times
- Error patterns

## Fallback Strategies

If automated data collection becomes problematic:
1. Increase cache durations to reduce request frequency
2. Implement manual triggering options
3. Reduce the number of events being tracked

This framework provides a robust approach to collecting secondary ticket market data while minimizing detection risk through sophisticated browser automation and natural request patterns.
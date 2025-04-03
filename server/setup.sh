#!/bin/bash
# Setup script for StubHub Proxy API Server

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Install dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Install Playwright browsers
echo "Installing Playwright browsers..."
playwright install
playwright install-deps

# Create .env if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.template .env
    echo "Please edit .env with your configuration"
fi

# Create logs directory
echo "Creating logs directory..."
mkdir -p logs

echo ""
echo "Setup complete! To start the server, run:"
echo "source .venv/bin/activate"
echo "uvicorn main:app --reload"
echo ""
echo "Or with Docker:"
echo "docker-compose up -d"

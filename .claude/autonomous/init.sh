#!/bin/bash
set -e

echo "Starting OneStack development environment..."

PROJECT_DIR="/Users/andreynovikov/workspace/tech/projects/kvota/onestack"
cd "$PROJECT_DIR"

check_port() {
    lsof -i :$1 2>/dev/null | grep LISTEN > /dev/null 2>&1
}

# Check Python virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Checking dependencies..."
pip install -q -r requirements.txt 2>/dev/null || {
    echo "Installing dependencies..."
    pip install -r requirements.txt
}

# Check if python-telegram-bot is installed (new dependency)
pip show python-telegram-bot > /dev/null 2>&1 || {
    echo "Installing python-telegram-bot..."
    pip install python-telegram-bot
}

# Check .env file
if [ ! -f ".env" ]; then
    echo "WARNING: .env file not found!"
    echo "Copy .env.example to .env and configure:"
    echo "  cp .env.example .env"
    exit 1
fi

# Check required environment variables
source .env
if [ -z "$SUPABASE_URL" ] || [ -z "$SUPABASE_ANON_KEY" ]; then
    echo "ERROR: SUPABASE_URL or SUPABASE_ANON_KEY not set in .env"
    exit 1
fi

PORT=5001

# Start server if not running
if check_port $PORT; then
    echo "Server already running on port $PORT"
else
    echo "Starting FastHTML server on port $PORT..."
    python main.py &
    sleep 3

    if check_port $PORT; then
        echo "Server started successfully"
    else
        echo "WARNING: Server may not have started. Check logs."
    fi
fi

echo ""
echo "Environment ready!"
echo "  App: http://localhost:$PORT"
echo "  Supabase: $SUPABASE_URL"
echo ""
echo "Useful commands:"
echo "  python main.py          # Run server"
echo "  deactivate              # Exit venv"

#!/bin/bash
# Reliable Reflex restart script

set -e

echo "=== Stopping Reflex ==="

# Find and kill processes on port 3000
PORT_3000_PIDS=$(ss -tlnp | grep ':3000' | grep -oP 'pid=\K[0-9]+' | sort -u || true)
if [ -n "$PORT_3000_PIDS" ]; then
    echo "Killing processes on port 3000: $PORT_3000_PIDS"
    echo "$PORT_3000_PIDS" | xargs -r kill -9
fi

# Find and kill processes on port 8000
PORT_8000_PIDS=$(ss -tlnp | grep ':8000' | grep -oP 'pid=\K[0-9]+' | sort -u || true)
if [ -n "$PORT_8000_PIDS" ]; then
    echo "Killing processes on port 8000: $PORT_8000_PIDS"
    echo "$PORT_8000_PIDS" | xargs -r kill -9
fi

# Kill any remaining reflex-related processes
pkill -9 -f "reflex run" || true
pkill -9 -f "bun run prod" || true

# Wait for ports to be released
echo "Waiting for ports to be released..."
sleep 3

# Verify ports are free
if ss -tlnp | grep -E ':(3000|8000)' > /dev/null; then
    echo "ERROR: Ports still in use after cleanup!"
    ss -tlnp | grep -E ':(3000|8000)'
    exit 1
fi

echo "✓ All processes stopped, ports are free"
echo ""
echo "=== Starting Reflex ==="

# Clear cache
rm -rf .web/__pycache__ streamscene/__pycache__ streamscene/pages/__pycache__

# Start Reflex
source venv/bin/activate
reflex run --env prod --loglevel info

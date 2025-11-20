#!/bin/bash
# Fix captive portal port 80 permissions

echo "=== Fixing Captive Portal Permissions ==="
echo ""

# Find the Python binary in the venv
VENV_PYTHON="$HOME/streamscene-client/venv/bin/python3"

if [ ! -f "$VENV_PYTHON" ]; then
    echo "ERROR: Virtual environment Python not found at $VENV_PYTHON"
    exit 1
fi

echo "1. Found Python binary: $VENV_PYTHON"
echo ""

echo "2. Current capabilities:"
getcap "$VENV_PYTHON"
echo ""

echo "3. Applying CAP_NET_BIND_SERVICE capability..."
sudo setcap 'cap_net_bind_service=+ep' "$VENV_PYTHON"

if [ $? -eq 0 ]; then
    echo "   ✓ setcap applied successfully"
else
    echo "   ✗ setcap failed"
    exit 1
fi
echo ""

echo "4. Verifying capabilities:"
getcap "$VENV_PYTHON"
echo ""

echo "=== Fix Complete ==="
echo "You can now run: python3 main.py"
echo "The portal server should be able to bind to port 80"

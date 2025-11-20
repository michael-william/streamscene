#!/bin/bash
# Clean up StreamScene client directory on Pi
# Run this before deployment to fix permission issues

PI_HOST="${1:-badgy@192.168.1.41}"
PI_DIR="~/streamscene-client"

echo "Cleaning up StreamScene client on $PI_HOST..."
echo ""

# Stop service if running
ssh $PI_HOST "sudo systemctl stop streamscene-client 2>/dev/null || true"

# Fix ownership and clean up
ssh $PI_HOST "
    sudo chown -R badgy:badgy $PI_DIR 2>/dev/null || true
    rm -rf $PI_DIR/output/*.png 2>/dev/null || true
    rm -rf $PI_DIR/venv 2>/dev/null || true
    rm -f $PI_DIR/*.log 2>/dev/null || true
    rm -f $PI_DIR/device_state.json 2>/dev/null || true
    rm -f $PI_DIR/wifi_credentials.json 2>/dev/null || true
"

echo "✓ Cleanup complete"
echo ""
echo "Now run: ./deploy_to_pi.sh $PI_HOST"

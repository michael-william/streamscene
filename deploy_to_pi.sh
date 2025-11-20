#!/bin/bash
# Deploy StreamScene client to Raspberry Pi
# Usage: ./deploy_to_pi.sh [PI_HOST]
#
# Optional argument:
#   PI_HOST - SSH host (default: badgy@192.168.1.41)

set -e

PI_HOST="${1:-badgy@192.168.1.41}"
PI_DIR="~/streamscene-client"

echo "🚀 StreamScene Client Deployment Script"
echo "========================================="
echo ""
echo "Target: $PI_HOST"
echo "Directory: $PI_DIR"
echo ""

# Create deployment archive
echo "📦 Creating deployment package..."
cd /root/streamscene
tar czf /tmp/streamscene-client.tar.gz \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='*.log' \
  --exclude='output/*.png' \
  --exclude='venv' \
  --exclude='.git' \
  -C client .

echo "✅ Package created: $(du -h /tmp/streamscene-client.tar.gz | cut -f1)"
echo ""

# Transfer to Pi
echo "📤 Transferring to Raspberry Pi..."
scp /tmp/streamscene-client.tar.gz ${PI_HOST}:/tmp/

echo "✅ Transfer complete"
echo ""

# Extract on Pi
echo "📂 Extracting on Raspberry Pi..."
ssh ${PI_HOST} "mkdir -p ${PI_DIR} && cd ${PI_DIR} && tar xzf /tmp/streamscene-client.tar.gz && rm /tmp/streamscene-client.tar.gz"

echo "✅ Extraction complete"
echo ""

# Run installation
echo "🔧 Running installation..."
ssh ${PI_HOST} "cd ${PI_DIR} && chmod +x install.sh provision.sh && ./install.sh"

echo "✅ Installation complete"
echo ""

# Get device UUID
echo "🔍 Checking device UUID..."
DEVICE_UUID=$(ssh ${PI_HOST} "cat /boot/firmware/streamscene-device.txt 2>/dev/null | grep -oP 'DEVICE_UUID=\K.*|^[0-9a-f-]{36}$' | head -1" || echo "")

if [ -n "$DEVICE_UUID" ]; then
    echo "✅ Device UUID: $DEVICE_UUID"
    REGISTRATION_URL="https://streamscene.dataandstories.com/setup?device_id=$DEVICE_UUID"
else
    echo "⚠ No device UUID found"
    echo "  Run provision.sh on the Pi to set up device UUID"
    REGISTRATION_URL="https://streamscene.dataandstories.com/setup"
fi
echo ""

# Check service status
echo "📊 Checking service status..."
SERVICE_STATUS=$(ssh ${PI_HOST} "systemctl is-active streamscene-client" || echo "inactive")

if [ "$SERVICE_STATUS" = "active" ]; then
    echo "✅ Service is running"
else
    echo "⚠ Service is not running"
    echo "  Start with: ssh ${PI_HOST} 'sudo systemctl start streamscene-client'"
fi
echo ""

echo "=========================================="
echo "✅ Deployment Complete!"
echo "=========================================="
echo ""
echo "Quick Commands:"
echo "  SSH to Pi:      ssh ${PI_HOST}"
echo "  View logs:      ssh ${PI_HOST} 'journalctl -u streamscene-client -f'"
echo "  Restart:        ssh ${PI_HOST} 'sudo systemctl restart streamscene-client'"
echo "  Check status:   ssh ${PI_HOST} 'sudo systemctl status streamscene-client'"
echo ""
if [ -n "$DEVICE_UUID" ]; then
    echo "Registration:"
    echo "  Device UUID: $DEVICE_UUID"
    echo "  URL: $REGISTRATION_URL"
    echo ""
fi
echo "Next Steps:"
echo "  1. Ensure service is running (see commands above)"
echo "  2. Device will enter WiFi setup mode if not configured"
echo "  3. Register device via web UI at registration URL"
echo ""

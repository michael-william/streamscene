#!/bin/bash
# StreamScene Client First Boot Provisioning Script
#
# This script runs ONCE on the first boot of a StreamScene device to:
# 1. Generate a unique device UUID
# 2. Create device ID file in /boot/firmware/
# 3. Enable and start the streamscene-client service
# 4. Create log directory
# 5. Self-delete after successful execution
#
# This script should be triggered by systemd on first boot

set -e

LOGFILE="/var/log/streamscene-firstboot.log"
DEVICE_ID_FILE="/boot/firmware/streamscene-device.txt"
CLIENT_SERVICE="streamscene-client.service"
LOG_DIR="/var/log/streamscene"

# Create log file
mkdir -p "$(dirname "$LOGFILE")"
exec &> >(tee -a "$LOGFILE")

echo "=================================================="
echo "StreamScene Client First Boot Provisioning"
echo "=================================================="
echo "Start time: $(date)"
echo ""

# Step 1: Generate unique device UUID
echo "[1/5] Generating unique device UUID..."
DEVICE_UUID=$(python3 -c 'import uuid; print(str(uuid.uuid4()))')
echo "Generated UUID: $DEVICE_UUID"
echo ""

# Step 2: Write device UUID to /boot/firmware/
echo "[2/5] Writing device UUID to $DEVICE_ID_FILE..."
echo "$DEVICE_UUID" | sudo tee "$DEVICE_ID_FILE" > /dev/null
sudo chmod 644 "$DEVICE_ID_FILE"
echo "Device ID file created successfully"
echo ""

# Step 3: Create log directory with correct permissions
echo "[3/5] Creating log directory: $LOG_DIR..."
sudo mkdir -p "$LOG_DIR"
sudo chown pi:pi "$LOG_DIR"
sudo chmod 755 "$LOG_DIR"
echo "Log directory created successfully"
echo ""

# Step 4: Enable and start StreamScene client service
echo "[4/5] Enabling StreamScene client service..."
sudo systemctl enable "$CLIENT_SERVICE"
echo "Service enabled"
echo ""

echo "[4/5] Starting StreamScene client service..."
sudo systemctl start "$CLIENT_SERVICE"
echo "Service started"
echo ""

# Step 5: Verify service is running
echo "[5/5] Verifying service status..."
if sudo systemctl is-active --quiet "$CLIENT_SERVICE"; then
    echo "✓ StreamScene client service is running!"
else
    echo "✗ Warning: Service may not have started correctly"
    echo "Check status with: sudo systemctl status $CLIENT_SERVICE"
fi
echo ""

# Display registration info
echo "=================================================="
echo "First Boot Provisioning Complete!"
echo "=================================================="
echo "Device UUID: $DEVICE_UUID"
echo "Device ID file: $DEVICE_ID_FILE"
echo "Service status: $(systemctl is-active $CLIENT_SERVICE)"
echo ""
echo "The device will now:"
echo "1. Create a WiFi hotspot (if no credentials saved)"
echo "2. Display a QR code for registration"
echo "3. Connect to WiFi once configured"
echo ""
echo "View logs with:"
echo "  sudo journalctl -u $CLIENT_SERVICE -f"
echo "  ~/streamscene-client/view_logs.sh all"
echo "=================================================="
echo ""

# Self-delete this script
echo "Removing first boot script (one-time execution)..."
sudo rm -f /etc/systemd/system/streamscene-firstboot.service
sudo systemctl daemon-reload
rm -f "$0"

echo "First boot provisioning complete at $(date)"
echo "System will continue normal operation"

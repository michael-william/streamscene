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
echo "[1/9] Generating unique device UUID..."
DEVICE_UUID=$(python3 -c 'import uuid; print(str(uuid.uuid4()))')
echo "Generated UUID: $DEVICE_UUID"
echo ""

# Step 2: Unblock WiFi (remove any rfkill blocks)
echo "[2/9] Unblocking WiFi..."
sudo rfkill unblock wifi 2>/dev/null || true
sudo rfkill unblock all 2>/dev/null || true
echo "WiFi unblocked"
echo ""

# Step 3: Write device UUID to /boot/firmware/
echo "[3/9] Writing device UUID to $DEVICE_ID_FILE..."
echo "$DEVICE_UUID" | sudo tee "$DEVICE_ID_FILE" > /dev/null
sudo chmod 644 "$DEVICE_ID_FILE"
echo "Device ID file created successfully"
echo ""

# Step 4: Disable NetworkManager (prevents conflicts with manual network control)
echo "[4/9] Disabling NetworkManager..."
sudo systemctl disable NetworkManager 2>/dev/null || true
sudo systemctl mask NetworkManager 2>/dev/null || true
sudo systemctl stop NetworkManager 2>/dev/null || true
echo "NetworkManager disabled"
echo ""

# Step 5: (removed) setcap on the system Python
# Port 80 binding is granted by AmbientCapabilities=CAP_NET_BIND_SERVICE on
# streamscene-client.service instead. Patching the interpreter gave every
# Python process on the device the same privilege and was silently reverted by
# any apt upgrade of python3.
echo "[5/9] Port 80 binding handled by systemd AmbientCapabilities - nothing to do"
echo ""

# Step 6: Create log directory with correct permissions
echo "[6/9] Creating log directory: $LOG_DIR..."
sudo mkdir -p "$LOG_DIR"
sudo chown pi:pi "$LOG_DIR"
sudo chmod 755 "$LOG_DIR"
echo "Log directory created successfully"
echo ""

# Step 7: Verify virtual environment exists (pre-installed during image build)
echo "[7/7] Verifying Python virtual environment..."
if [ -d /home/pi/streamscene-client/venv ] && [ -f /home/pi/streamscene-client/venv/bin/python3 ]; then
    echo "✓ Virtual environment found (pre-installed in image)"
else
    echo "✗ Warning: Virtual environment not found or incomplete!"
    echo "  This should have been created during image build"
    echo "  Attempting to create venv now..."
    cd /home/pi/streamscene-client
    python3 -m venv venv
    /home/pi/streamscene-client/venv/bin/pip install --upgrade pip --quiet
    /home/pi/streamscene-client/venv/bin/pip install -r requirements.txt --quiet || echo "Failed to install dependencies"
fi
echo ""

# Step 8: Enable and start StreamScene client service
echo "[7/7] Enabling StreamScene client service..."
sudo systemctl enable "$CLIENT_SERVICE"
echo "Service enabled"
echo ""

echo ""

# NOTE: do not check is-active here.
# This unit is ordered Before=streamscene-client.service, so the client has not
# started yet by definition. The old check always reported
# "Service may not have started correctly" on a perfectly healthy first boot,
# which sent people debugging a non-problem.
echo "[7/7] Service enabled; it starts after this unit completes."
echo ""

# Display registration info
echo "=================================================="
echo "First Boot Provisioning Complete!"
echo "=================================================="
echo "Device UUID: $DEVICE_UUID"
echo "Device ID file: $DEVICE_ID_FILE"
echo "Service: enabled (starts once this unit finishes)"
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
sudo rm -f /etc/systemd/system/multi-user.target.wants/streamscene-firstboot.service
sudo systemctl daemon-reload
rm -f "$0"

echo "First boot provisioning complete at $(date)"
echo "System will continue normal operation"

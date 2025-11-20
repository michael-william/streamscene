#!/bin/bash
# StreamScene Device Provisioning Script
# Run this to set up a unique device UUID for each StreamScene frame
#
# Usage: ./provision.sh [UUID]
#   If UUID is not provided, a new one will be generated

set -e

echo "=========================================="
echo "StreamScene Device Provisioning"
echo "=========================================="
echo ""

UUID_FILE="/boot/firmware/streamscene-device.txt"

# Check if UUID was provided as argument
if [ -n "$1" ]; then
    DEVICE_UUID="$1"
    echo "Using provided UUID: $DEVICE_UUID"
else
    # Check if UUID already exists
    if [ -f "$UUID_FILE" ]; then
        EXISTING_UUID=$(cat "$UUID_FILE" | grep -oP 'DEVICE_UUID=\K.*|^[0-9a-f-]{36}$' | head -1)
        if [ -n "$EXISTING_UUID" ]; then
            echo "⚠ Device UUID already exists: $EXISTING_UUID"
            read -p "Generate new UUID? This will replace the existing one (y/n): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                echo "Keeping existing UUID: $EXISTING_UUID"
                DEVICE_UUID="$EXISTING_UUID"
            else
                DEVICE_UUID=$(uuidgen)
                echo "Generated new UUID: $DEVICE_UUID"
            fi
        else
            DEVICE_UUID=$(uuidgen)
            echo "Generated new UUID: $DEVICE_UUID"
        fi
    else
        DEVICE_UUID=$(uuidgen)
        echo "Generated new UUID: $DEVICE_UUID"
    fi
fi

# Validate UUID format
if ! echo "$DEVICE_UUID" | grep -qP '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'; then
    echo "✗ Invalid UUID format: $DEVICE_UUID"
    exit 1
fi

echo ""
echo "Step 1: Writing UUID to Boot Partition"
echo "---------------------------------------"

# Write UUID to boot partition
echo "DEVICE_UUID=$DEVICE_UUID" | sudo tee "$UUID_FILE" > /dev/null

# Verify it was written
if [ -f "$UUID_FILE" ]; then
    WRITTEN_UUID=$(cat "$UUID_FILE")
    echo "✓ UUID written to $UUID_FILE"
    echo "  Content: $WRITTEN_UUID"
else
    echo "✗ Failed to write UUID file"
    exit 1
fi

echo ""
echo "Step 2: Generating QR Code"
echo "--------------------------"

REGISTRATION_URL="https://streamscene.dataandstories.com/setup?device_id=$DEVICE_UUID"
QR_OUTPUT="$HOME/device-$DEVICE_UUID-qr.png"

if command -v qrencode &> /dev/null; then
    qrencode -o "$QR_OUTPUT" "$REGISTRATION_URL"
    echo "✓ QR code generated: $QR_OUTPUT"
    echo "  Print this and stick it on the device frame"
    echo "  URL: $REGISTRATION_URL"
else
    echo "⚠ qrencode not installed, skipping QR code generation"
    echo "  Install with: sudo apt-get install qrencode"
    echo "  Registration URL: $REGISTRATION_URL"
fi

echo ""
echo "Step 3: Service Management"
echo "--------------------------"

# Check if service is installed
if systemctl list-unit-files | grep -q streamscene-client.service; then
    echo "StreamScene client service is installed"

    # Check if service is running
    if systemctl is-active --quiet streamscene-client; then
        echo "⚠ Service is currently running"
        read -p "Restart service to apply new UUID? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            sudo systemctl restart streamscene-client
            echo "✓ Service restarted"
        fi
    else
        echo "Service is not running"
        read -p "Start service now? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            sudo systemctl start streamscene-client
            echo "✓ Service started"
        fi
    fi

    echo ""
    echo "Service commands:"
    echo "  Status: sudo systemctl status streamscene-client"
    echo "  Start:  sudo systemctl start streamscene-client"
    echo "  Stop:   sudo systemctl stop streamscene-client"
    echo "  Logs:   journalctl -u streamscene-client -f"
else
    echo "⚠ StreamScene client service not installed"
    echo "  Run install.sh first"
fi

echo ""
echo "=========================================="
echo "Provisioning Complete!"
echo "=========================================="
echo ""
echo "Device Information:"
echo "  UUID: $DEVICE_UUID"
echo "  QR Code: $QR_OUTPUT"
echo "  Registration URL: $REGISTRATION_URL"
echo ""
echo "Next Steps:"
echo "  1. Print and attach QR code to device"
echo "  2. Ensure service is running (see commands above)"
echo "  3. Device will show WiFi setup on E Ink display"
echo "  4. Connect to WiFi hotspot and configure"
echo "  5. Scan QR code to register device via web UI"
echo ""

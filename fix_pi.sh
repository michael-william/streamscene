#!/bin/bash
# StreamScene Pi Fix Script
# This script fixes the hotspot and starts the client

echo "=========================================="
echo "StreamScene Pi Fix Script"
echo "=========================================="
echo ""

cd ~/streamscene-client

echo "Step 1: Stop current hotspot"
echo "-----------------------------"
sudo systemctl stop hostapd
sudo systemctl stop dnsmasq
sleep 2

echo ""
echo "Step 2: Restart hotspot with dnsmasq"
echo "-------------------------------------"
python3 << 'EOF'
import sys
sys.path.insert(0, '/home/badgy/streamscene-client')

from setup.hotspot import create_hotspot, generate_ssid

device_uuid = "1c91d1e9-3cc9-44ba-a008-9cdee188d90c"
ssid = generate_ssid(device_uuid)

print(f"Creating hotspot: {ssid}")
print(f"Password: streamscene")

if create_hotspot(ssid, "streamscene"):
    print("✓ Hotspot created successfully")
else:
    print("✗ Hotspot creation failed")
    sys.exit(1)
EOF

echo ""
echo "Step 3: Verify services"
echo "-----------------------"
sleep 3
echo "hostapd status: $(sudo systemctl is-active hostapd)"
echo "dnsmasq status: $(sudo systemctl is-active dnsmasq)"

echo ""
echo "Step 4: Check network configuration"
echo "------------------------------------"
ip addr show wlan0 | grep inet

echo ""
echo "=========================================="
echo "Fix Complete!"
echo "=========================================="
echo ""
echo "Now try connecting to: StreamScene-E188"
echo "Password: streamscene"
echo "You should be able to reach: http://192.168.4.1"
echo ""

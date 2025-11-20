#!/bin/bash
# Configure StreamScene Pi for Production (External Domain Access)
# This sets up the device to use streamscene.dataandstories.com

echo "=========================================="
echo "StreamScene Pi Production Setup"
echo "=========================================="
echo ""

cd ~/streamscene-client

echo "Step 1: Verify Domain Access"
echo "-----------------------------"
echo "Testing: https://streamscene.dataandstories.com"
if curl -s --max-time 10 https://streamscene.dataandstories.com/api/devices/1c91d1e9-3cc9-44ba-a008-9cdee188d90c/registration-status > /dev/null; then
    echo "✓ Domain is accessible"
else
    echo "✗ Cannot reach domain"
    echo "  Check DNS and internet connectivity"
    exit 1
fi
echo ""

echo "Step 2: Stop Hotspot Services"
echo "-----------------------------"
echo "Stopping hotspot (not needed when on home WiFi)..."
sudo systemctl stop hostapd 2>/dev/null
sudo systemctl stop dnsmasq 2>/dev/null
sudo systemctl mask hostapd 2>/dev/null  # Prevent auto-restart
sleep 2
echo "✓ Hotspot services stopped and disabled"
echo ""

echo "Step 3: Enable WiFi Client Mode"
echo "--------------------------------"
sudo systemctl unmask wpa_supplicant 2>/dev/null
sudo systemctl start wpa_supplicant
sleep 2
echo "✓ WiFi client mode enabled"
echo ""

echo "Step 4: Connect to Home WiFi"
echo "----------------------------"
python3 << 'EOF'
import sys
sys.path.insert(0, '/home/badgy/streamscene-client')

from setup.wifi_client import connect_to_wifi, get_ip_address, is_connected

ssid = "Louisiamsterdam-TP"
password = "Tailgate2011"

if is_connected():
    print(f"✓ Already connected to WiFi")
    ip = get_ip_address()
    print(f"  IP: {ip}")
else:
    print(f"Connecting to: {ssid}")
    if connect_to_wifi(ssid, password, timeout=30):
        ip = get_ip_address()
        print(f"✓ Connected successfully")
        print(f"  IP: {ip}")
    else:
        print(f"⚠ WiFi connection failed")
        print(f"  (Continuing - Ethernet is available)")
EOF
echo ""

echo "Step 5: Configure Production API URL"
echo "-------------------------------------"
# Create environment file
cat > ~/.streamscene_env << 'ENVEOF'
# StreamScene Production Configuration
export STREAMSCENE_API_URL="https://streamscene.dataandstories.com"
export STREAMSCENE_DISPLAY_MODE="headless"
ENVEOF

# Add to .bashrc if not already there
if ! grep -q "source ~/.streamscene_env" ~/.bashrc; then
    echo "" >> ~/.bashrc
    echo "# StreamScene environment" >> ~/.bashrc
    echo "source ~/.streamscene_env" >> ~/.bashrc
    echo "✓ Added to ~/.bashrc (will load on login)"
fi

# Source it now
source ~/.streamscene_env
echo "✓ API URL configured: $STREAMSCENE_API_URL"
echo ""

echo "Step 6: Test API Connection"
echo "---------------------------"
curl -s https://streamscene.dataandstories.com/api/devices/1c91d1e9-3cc9-44ba-a008-9cdee188d90c/registration-status | python3 -m json.tool
echo ""

echo "Step 7: Reset Device State"
echo "--------------------------"
python3 << 'EOF'
import sys
import json
sys.path.insert(0, '/home/badgy/streamscene-client')

from states import StateMachine, DeviceState

sm = StateMachine(device_uuid="1c91d1e9-3cc9-44ba-a008-9cdee188d90c")
print(f"Current state: {sm.current_state.value}")

# Move to awaiting_registration since WiFi is already configured
sm.transition_to(DeviceState.AWAITING_REGISTRATION, {
    "ssid": "Louisiamsterdam-TP",
    "configured": True
})
print(f"✓ State set to: {sm.current_state.value}")
EOF
echo ""

echo "Step 8: Stop Any Running Client"
echo "--------------------------------"
if pgrep -f "python3.*main.py" > /dev/null; then
    echo "Stopping existing client..."
    pkill -f "python3.*main.py"
    sleep 2
    echo "✓ Stopped"
else
    echo "No client running"
fi
echo ""

echo "Step 9: Start StreamScene Client"
echo "---------------------------------"
# Start with production settings
export STREAMSCENE_API_URL="https://streamscene.dataandstories.com"
export STREAMSCENE_DISPLAY_MODE="headless"

echo "Starting client with:"
echo "  API URL: $STREAMSCENE_API_URL"
echo "  Display Mode: $STREAMSCENE_DISPLAY_MODE"
echo ""

nohup python3 main.py > client.log 2>&1 &
CLIENT_PID=$!

sleep 4

if ps -p $CLIENT_PID > /dev/null; then
    echo "✓ Client started successfully (PID: $CLIENT_PID)"
    echo ""
    echo "Checking initial log output:"
    tail -15 client.log
else
    echo "✗ Client failed to start"
    echo ""
    echo "Error log:"
    tail -30 client.log
    exit 1
fi

echo ""
echo "=========================================="
echo "Production Setup Complete!"
echo "=========================================="
echo ""
echo "Your device is now configured to use:"
echo "  https://streamscene.dataandstories.com"
echo ""
echo "Next Steps:"
echo "  1. Device is in 'awaiting_registration' state"
echo "  2. Register it via the web interface:"
echo "     https://streamscene.dataandstories.com/setup?device_id=1c91d1e9-3cc9-44ba-a008-9cdee188d90c"
echo "  3. Once registered, device will go online automatically"
echo ""
echo "Useful Commands:"
echo "  View logs:     tail -f ~/streamscene-client/client.log"
echo "  Stop client:   pkill -f 'python3.*main.py'"
echo "  Restart:       ~/configure_pi_production.sh"
echo "  Check status:  ps aux | grep main.py"
echo ""

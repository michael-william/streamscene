#!/bin/bash
# StreamScene Pi Investigation Script
# Run this to understand current state and what needs fixing

echo "=========================================="
echo "StreamScene Pi Investigation"
echo "=========================================="
echo ""

cd ~/streamscene-client

echo "1. Current Device State"
echo "----------------------"
if [ -f device_state.json ]; then
    cat device_state.json
    echo ""
else
    echo "No device_state.json found"
fi
echo ""

echo "2. WiFi Credentials Saved"
echo "-------------------------"
if [ -f wifi_credentials.json ]; then
    cat wifi_credentials.json
    echo ""
else
    echo "No wifi_credentials.json found"
fi
echo ""

echo "3. Client Directory Contents"
echo "----------------------------"
ls -lh
echo ""

echo "4. Setup Directory Contents"
echo "---------------------------"
ls -lh setup/
echo ""

echo "5. Output Directory (rendered images)"
echo "--------------------------------------"
if [ -d output ]; then
    ls -lh output/
else
    echo "No output directory"
fi
echo ""

echo "6. Check for Log Files"
echo "----------------------"
find . -name "*.log" -type f -exec ls -lh {} \; 2>/dev/null || echo "No log files found"
echo ""

echo "7. Python Dependencies Check"
echo "----------------------------"
echo "Checking if required Python packages are installed..."
python3 -c "
import sys
packages = ['PIL', 'requests', 'qrcode']
missing = []
for pkg in packages:
    try:
        __import__(pkg)
        print(f'✓ {pkg}')
    except ImportError:
        print(f'✗ {pkg} - MISSING')
        missing.append(pkg)

if missing:
    print(f'\nMissing packages: {missing}')
    print('Install with: pip3 install pillow requests qrcode')
else:
    print('\n✓ All required packages installed')
"
echo ""

echo "8. Test Config Loading"
echo "----------------------"
python3 << 'EOF'
import sys
sys.path.insert(0, '/home/badgy/streamscene-client')

try:
    import config
    print(f"✓ Config module loads successfully")
    print(f"  Device ID: {config.DEVICE_ID}")
    print(f"  API Base URL: {config.API_BASE_URL}")
    print(f"  Display Mode: {config.DISPLAY_MODE}")
    print(f"  API Key present: {'Yes' if config.API_KEY else 'No'}")
except Exception as e:
    print(f"✗ Config error: {e}")
EOF
echo ""

echo "9. Test State Machine Loading"
echo "-----------------------------"
python3 << 'EOF'
import sys
sys.path.insert(0, '/home/badgy/streamscene-client')

try:
    from states import StateMachine
    sm = StateMachine(device_uuid="1c91d1e9-3cc9-44ba-a008-9cdee188d90c")
    print(f"✓ State machine loads successfully")
    print(f"  Current state: {sm.current_state.value}")
    print(f"  State file: {sm.state_file}")
except Exception as e:
    print(f"✗ State machine error: {e}")
    import traceback
    traceback.print_exc()
EOF
echo ""

echo "10. Test API Client Connection"
echo "------------------------------"
python3 << 'EOF'
import sys
sys.path.insert(0, '/home/badgy/streamscene-client')

try:
    from api_client import StreamSceneAPIClient

    # Try to create client (won't connect yet, just test initialization)
    client = StreamSceneAPIClient(
        base_url="http://192.168.1.118:8000",
        device_id="1c91d1e9-3cc9-44ba-a008-9cdee188d90c",
        api_key=None  # Will check registration status
    )
    print(f"✓ API client initialized")

    # Try to check registration status (unauthenticated endpoint)
    print(f"\nChecking registration status with server...")
    status = client.check_registration_status()

    if status:
        print(f"✓ Server responded")
        print(f"  Registered: {status.get('is_registered', False)}")
        print(f"  Nickname: {status.get('nickname', 'N/A')}")
        if status.get('api_key'):
            print(f"  API Key available: Yes (will be saved)")
    else:
        print(f"✗ No response from server")

except Exception as e:
    print(f"✗ API client error: {e}")
    import traceback
    traceback.print_exc()
EOF
echo ""

echo "11. Network Services Status"
echo "---------------------------"
echo "hostapd: $(sudo systemctl is-active hostapd)"
echo "dnsmasq: $(sudo systemctl is-active dnsmasq)"
echo "wpa_supplicant: $(sudo systemctl is-active wpa_supplicant)"
echo ""

echo "12. Network Interface Details"
echo "-----------------------------"
ip addr show wlan0
echo ""

echo "13. Can Reach Server API?"
echo "-------------------------"
curl -s http://192.168.1.118:8000/api/devices/1c91d1e9-3cc9-44ba-a008-9cdee188d90c/registration-status | python3 -m json.tool 2>/dev/null || echo "Could not reach API or parse response"
echo ""

echo "=========================================="
echo "Investigation Complete!"
echo "=========================================="
echo ""
echo "Next steps will depend on findings above."

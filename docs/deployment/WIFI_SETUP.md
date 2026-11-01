# WiFi Setup Deployment Guide

> ## ⚠️ Development and testing only
>
> **This is not the distribution process.** It describes Environment A - a Pi
> on your bench, reachable over a USB-ethernet adapter, with packages installed
> by hand and client code rsynced over. Devices you hand to other people have
> no ethernet and none of these manual steps.
>
> - To build and hand out a device → **[DISTRIBUTION.md](DISTRIBUTION.md)**
> - For image internals → [SD_CARD_IMAGE.md](SD_CARD_IMAGE.md)
> - To debug a device at someone else's house →
>   [../development/REMOTE_DEBUG.md](../development/REMOTE_DEBUG.md)
>
> Following this guide when you meant to produce a distributable card is the
> single most common way to end up with a device that does nothing.
>
> **Two details below are stale** and kept only because the surrounding manual
> procedure still works on a bench Pi:
> - The device UUID path is `/boot/firmware/streamscene-device.txt` on Bookworm,
>   not `/boot/streamscene-device.txt`.
> - The production image is **32-bit (armhf)**, not 64-bit.

This guide explains how to deploy and test the WiFi hotspot and captive portal functionality on your Raspberry Pi Zero 2 WH.

## Prerequisites

### Hardware
- ✅ Raspberry Pi Zero 2 WH (with WiFi)
- ✅ Waveshare 7.3" 6-color E Ink display (connected)
- ✅ Ethernet cable (for testing - maintains SSH access)
- ✅ Power supply
- ✅ Phone or laptop (for testing captive portal)

### Software
- ✅ Raspberry Pi OS Lite (64-bit) installed
- ✅ SSH enabled
- ✅ WiFi working (verified earlier)

---

## Step 1: Install System Dependencies

**On your Raspberry Pi (via SSH):**

```bash
# Connect via ethernet
ssh badgy@streamscene.local

# Update package lists
sudo apt-get update

# Install required packages
sudo apt-get install -y hostapd dnsmasq

# Disable services (we'll control them manually)
sudo systemctl disable hostapd
sudo systemctl disable dnsmasq
sudo systemctl stop hostapd
sudo systemctl stop dnsmasq

# Install Python dependencies
pip3 install --upgrade pip
```

---

## Step 2: Deploy Client Code to Raspberry Pi

### Option A: Using rsync (Recommended for Testing)

**On your dev machine:**

```bash
# Navigate to project root
cd /root/streamscene

# Deploy client code to Pi
rsync -avz --progress client/ badgy@streamscene.local:~/streamscene-client/

# Verify deployment
ssh badgy@streamscene.local "ls -la ~/streamscene-client/"
```

### Option B: Using Git (For Production)

**On your Raspberry Pi:**

```bash
cd ~
git clone https://github.com/yourusername/streamscene.git
cd streamscene/client
cp -r . ~/streamscene-client/
```

---

## Step 3: Create Device UUID

**On your Raspberry Pi:**

```bash
# Generate a unique device UUID
DEVICE_UUID=$(uuidgen)
echo "DEVICE_UUID=$DEVICE_UUID" | sudo tee /boot/streamscene-device.txt

# Verify
cat /boot/streamscene-device.txt
```

---

## Step 4: Test WiFi Hotspot Creation

### Test 1: Create Hotspot

**On your Raspberry Pi (via ethernet SSH):**

```bash
cd ~/streamscene-client/setup

# Test hotspot creation (requires sudo)
sudo python3 hotspot.py

# Expected output:
# Creating WiFi hotspot: StreamScene-XXXX
# ✓ Hotspot created successfully: StreamScene-XXXX
#   IP Address: 192.168.4.1
#   Password: streamscene
```

**Verify:**
- On your phone: Look for WiFi network "StreamScene-XXXX"
- It should appear in available networks
- **Don't connect yet** - we haven't started the portal server

### Test 2: Stop Hotspot

```bash
# Stop the hotspot
sudo python3 hotspot.py stop

# Expected output:
# Stopping WiFi hotspot...
# ✓ Hotspot stopped successfully
```

**Verify:**
- WiFi network "StreamScene-XXXX" should disappear
- Your Pi should reconnect to home WiFi automatically

---

## Step 5: Test Captive Portal Server

### Test Portal (Standalone)

**On your Raspberry Pi:**

```bash
cd ~/streamscene-client/setup

# Start portal server on port 8080 (testing port)
python3 portal_server.py
```

**From another terminal (or your dev machine):**

```bash
# Test the portal
curl http://streamscene.local:8080/

# You should see HTML output for the setup page
```

**Stop the test server:** Press Ctrl+C

---

## Step 6: Full WiFi Setup Flow Test

This is the complete end-to-end test of the WiFi setup system.

### Step 6.1: Start Hotspot + Portal

**On your Raspberry Pi (via ethernet SSH):**

```bash
cd ~/streamscene-client

# Create a test script
cat > test_wifi_setup.py << 'EOF'
#!/usr/bin/env python3
"""Test WiFi setup flow."""

import logging
import time
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from setup import (
    create_hotspot,
    generate_ssid,
    CaptivePortalServer,
    is_connected,
    connect_to_wifi,
    stop_hotspot
)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def main():
    # Step 1: Read device UUID
    try:
        with open('/boot/streamscene-device.txt', 'r') as f:
            line = f.read().strip()
            device_uuid = line.split('=')[1]
            print(f"Device UUID: {device_uuid}")
    except:
        device_uuid = "test-uuid-1234-5678"
        print(f"Using test UUID: {device_uuid}")

    # Step 2: Generate SSID
    ssid = generate_ssid(device_uuid)
    print(f"\n{'='*50}")
    print(f"Creating WiFi Hotspot")
    print(f"{'='*50}")
    print(f"SSID: {ssid}")
    print(f"Password: streamscene")
    print(f"Portal: http://192.168.4.1")
    print(f"{'='*50}\n")

    # Step 3: Create hotspot
    if not create_hotspot(ssid):
        print("❌ Failed to create hotspot")
        return

    # Step 4: Start captive portal
    print("\nStarting captive portal server...")
    portal = CaptivePortalServer(port=80)
    portal.start()

    print("\n" + "="*50)
    print("READY FOR TESTING")
    print("="*50)
    print("1. On your phone, connect to WiFi: " + ssid)
    print("2. Password: streamscene")
    print("3. Browser should auto-open captive portal")
    print("4. Enter your home WiFi credentials")
    print("5. Submit the form")
    print("="*50)
    print("\nWaiting for credentials (press Ctrl+C to cancel)...\n")

    # Step 5: Wait for credentials
    try:
        while not portal.has_credentials():
            time.sleep(1)

        print("\n✓ Credentials received!")
        creds = portal.get_credentials()
        print(f"  SSID: {creds['ssid']}")
        print(f"  Password: {'*' * len(creds.get('password', ''))}")

        # Step 6: Stop portal
        print("\nStopping captive portal...")
        portal.stop()

        # Step 7: Stop hotspot
        print("Stopping hotspot...")
        stop_hotspot()

        # Step 8: Connect to home WiFi
        print(f"\nConnecting to {creds['ssid']}...")
        if connect_to_wifi(creds['ssid'], creds.get('password', '')):
            print("\n✓ WiFi setup complete!")
            print("="*50)
        else:
            print("\n❌ Failed to connect to WiFi")

    except KeyboardInterrupt:
        print("\n\nCancelled by user")
        print("Cleaning up...")
        portal.stop()
        stop_hotspot()

if __name__ == "__main__":
    main()
EOF

chmod +x test_wifi_setup.py

# Run the test (requires sudo)
sudo python3 test_wifi_setup.py
```

### Step 6.2: Test from Your Phone

1. **Connect to StreamScene WiFi:**
   - Open WiFi settings on your phone
   - Find network "StreamScene-XXXX"
   - Password: `streamscene`
   - Connect

2. **Captive Portal Should Auto-Open:**
   - Your phone should automatically show the captive portal
   - If not, open browser and go to: `http://192.168.4.1`

3. **Enter WiFi Credentials:**
   - Enter your home WiFi network name
   - Enter your home WiFi password
   - Click "Connect to WiFi"

4. **Verify on Pi:**
   - The Pi terminal should show: "✓ Credentials received!"
   - It will automatically connect to your home WiFi
   - Check if connected: `ip addr show wlan0`

---

## Step 7: Verify Internet Connectivity

**After WiFi setup completes:**

```bash
# Check connection status
ping -c 3 8.8.8.8

# Check IP address
ip addr show wlan0

# Verify you can reach your server
curl http://192.168.1.118:8000/api/health
```

**Expected:** All tests should succeed

---

## Troubleshooting

### Problem: Hotspot won't start

```bash
# Check if services are running
sudo systemctl status hostapd
sudo systemctl status dnsmasq

# Check logs
sudo journalctl -u hostapd -n 50
sudo journalctl -u dnsmasq -n 50

# Verify wlan0 is up
ip link show wlan0
```

### Problem: Can't see hotspot on phone

```bash
# Check if hostapd is actually running
sudo systemctl is-active hostapd

# Verify wlan0 has the static IP
ip addr show wlan0 | grep "192.168.4.1"

# Check hostapd config
sudo cat /etc/hostapd/hostapd.conf
```

### Problem: Captive portal doesn't open

```bash
# Check if portal server is running
sudo netstat -tulpn | grep :80

# Test portal locally
curl http://192.168.4.1

# Check dnsmasq is redirecting DNS
sudo systemctl status dnsmasq
```

### Problem: Can't connect to home WiFi

```bash
# Check wpa_supplicant config
sudo cat /etc/wpa_supplicant/wpa_supplicant.conf

# Check wpa_supplicant status
sudo systemctl status wpa_supplicant

# Try manual connection
sudo wpa_supplicant -B -i wlan0 -c /etc/wpa_supplicant/wpa_supplicant.conf

# Check for IP address
ip addr show wlan0

# Request DHCP
sudo dhclient wlan0
```

---

## Success Criteria

✅ **Hotspot Creation:**
- WiFi network appears on phone
- Can connect with password "streamscene"

✅ **Captive Portal:**
- Portal auto-opens or accessible at http://192.168.4.1
- Form accepts credentials
- Success page displays

✅ **WiFi Connection:**
- Pi disconnects from hotspot
- Pi connects to home WiFi
- Pi gets IP address
- Pi has internet access

✅ **Ethernet Independence:**
- Throughout all tests, ethernet SSH connection remains active
- Can monitor logs in real-time

---

## Next Steps

After successful WiFi setup testing:

1. **Phase 5:** Device State Machine (registration, QR code display)
2. **Phase 6:** E Ink Display Integration (show setup screens)
3. **Phase 7:** OTA Update Client
4. **Phase 8:** systemd Service (auto-start on boot)

---

## Notes

- **Ethernet is for testing only** - in production, devices won't have ethernet
- **WiFi setup runs once** - after credentials saved, device auto-connects
- **Reset to test again:** Delete `/home/badgy/streamscene-client/wifi_credentials.json`
- **Security:** Password "streamscene" is hardcoded - fine for temporary setup network

---

## Quick Reference Commands

```bash
# Start hotspot + portal
sudo python3 ~/streamscene-client/test_wifi_setup.py

# Stop hotspot
sudo python3 ~/streamscene-client/setup/hotspot.py stop

# Check WiFi status
sudo python3 ~/streamscene-client/setup/wifi_client.py

# Reset credentials (to test again)
rm ~/streamscene-client/wifi_credentials.json

# View logs
sudo journalctl -u hostapd -f
sudo journalctl -u dnsmasq -f
```

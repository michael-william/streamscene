# StreamScene Raspberry Pi Client Troubleshooting Guide

## Quick Diagnostics

### Essential Commands

```bash
# View all logs in real-time
~/streamscene-client/view_logs.sh all

# View only errors
~/streamscene-client/view_logs.sh errors

# View recent activity
~/streamscene-client/view_logs.sh recent

# Check service status
sudo systemctl status streamscene-client

# View systemd journal
sudo journalctl -u streamscene-client -n 100

# Check network status
ip addr show wlan0
```

## Log Files Reference

### Location

All logs are in `/var/log/streamscene/`:

| Log File | Purpose | When to Check |
|----------|---------|---------------|
| `streamscene-client.log` | Main client activity | General issues, state transitions |
| `streamscene-hotspot.log` | WiFi hotspot creation/management | Hotspot not appearing |
| `streamscene-wifi.log` | WiFi client connection | Can't connect to home WiFi |
| `streamscene-registration.log` | Device registration process | Registration failures |

### Log Format

```
[TIMESTAMP] [LEVEL] [COMPONENT] message
```

Example:
```
[2025-01-17 10:23:45] [INFO] [HOTSPOT] Creating WiFi hotspot: StreamScene-ABC1
[2025-01-17 10:23:47] [ERROR] [HOTSPOT] Failed to start hostapd: [stderr output]
```

### Log Levels

- **INFO** - Normal operation
- **WARNING** - Non-critical issue (operation continues)
- **ERROR** - Critical issue (operation failed)
- **CRITICAL** - System-level failure

## Common Issues

### 1. Hotspot Not Appearing

#### Symptoms
- No `StreamScene-XXXX` network visible
- Can't access captive portal
- Device not accessible via SSH

#### Diagnostic Steps

1. **Check if service is running:**
   ```bash
   ssh pi@streamscene.local  # If you can still access
   sudo systemctl status streamscene-client
   ```

   Expected output:
   ```
   ● streamscene-client.service - StreamScene E Ink Client
        Loaded: loaded
        Active: active (running)
   ```

2. **Check hotspot logs:**
   ```bash
   cat /var/log/streamscene/streamscene-hotspot.log
   ```

   Look for:
   - `Creating WiFi hotspot: StreamScene-XXXX`
   - `hostapd is running and active`
   - `dnsmasq is running and active`

3. **Check for permission errors:**
   ```bash
   grep -i "permission denied" /var/log/streamscene/*.log
   ```

4. **Verify sudo permissions:**
   ```bash
   sudo -l -U pi | grep systemctl
   ```

   Should show network commands without `NOPASSWD`.

#### Common Causes

**A. Sudo permissions not configured**

**Solution:**
```bash
# Install sudoers file
sudo install -m 0440 ~/streamscene-client/config/sudoers.streamscene /etc/sudoers.d/streamscene

# Verify syntax
sudo visudo -c

# Restart service
sudo systemctl restart streamscene-client
```

**B. hostapd or dnsmasq not installed**

**Solution:**
```bash
sudo apt-get update
sudo apt-get install -y hostapd dnsmasq

# Disable auto-start (client manages these)
sudo systemctl disable hostapd
sudo systemctl disable dnsmasq

# Restart client
sudo systemctl restart streamscene-client
```

**C. wlan0 interface doesn't exist**

**Solution:**
```bash
# Check available interfaces
ip link show

# If wlan0 missing, check WiFi adapter
lsusb
dmesg | grep -i wifi

# Reboot may be needed
sudo reboot
```

**D. Another process is using wlan0**

**Solution:**
```bash
# Check what's using wlan0
sudo lsof | grep wlan0

# Kill NetworkManager if running (common issue)
sudo systemctl stop NetworkManager
sudo systemctl disable NetworkManager

# Restart client
sudo systemctl restart streamscene-client
```

### 2. WiFi Connection Fails

#### Symptoms
- Device creates hotspot successfully
- WiFi credentials submitted
- Device doesn't connect to home network
- Returns to hotspot mode

#### Diagnostic Steps

1. **Check WiFi logs:**
   ```bash
   cat /var/log/streamscene/streamscene-wifi.log
   ```

   Look for:
   - `Attempting to connect to SSID: YourNetwork`
   - `Successfully connected! IP address: 192.168.1.XXX`
   - OR error messages with failure reason

2. **Check saved credentials:**
   ```bash
   cat ~/streamscene-client/wifi_credentials.json
   ```

3. **Test connection manually:**
   ```bash
   # Stop client
   sudo systemctl stop streamscene-client

   # Try manual connection
   sudo wpa_cli -i wlan0 reconfigure
   sudo dhclient wlan0

   # Check status
   sudo wpa_cli -i wlan0 status
   ```

#### Common Causes

**A. Incorrect credentials**

**Solution:**
```bash
# Delete saved credentials
rm ~/streamscene-client/wifi_credentials.json

# Reset device state
rm ~/streamscene-client/device_state.json

# Restart to redo setup
sudo systemctl restart streamscene-client
```

**B. 5GHz network (Pi Zero 2 WH only supports 2.4GHz)**

**Solution:**
- Use 2.4GHz network instead
- Enable 2.4GHz on dual-band router

**C. Hidden SSID**

**Solution:**
Edit `/etc/wpa_supplicant/wpa_supplicant.conf`:
```
network={
    ssid="YourNetwork"
    psk="YourPassword"
    scan_ssid=1  # Add this line
}
```

**D. MAC address filtering**

**Solution:**
```bash
# Get device MAC address
ip link show wlan0 | grep link/ether

# Add MAC to router whitelist
```

### 3. Registration Timeout

#### Symptoms
- Device connects to WiFi
- QR code displayed
- No registration after scanning and submitting

#### Diagnostic Steps

1. **Check registration logs:**
   ```bash
   cat /var/log/streamscene/streamscene-registration.log
   ```

   Look for:
   - `Starting registration polling`
   - `Registration URL: https://...`
   - Poll attempts every 10 seconds

2. **Test server connectivity:**
   ```bash
   # Ping server
   ping -c 3 streamscene.dataandstories.com

   # Test HTTPS
   curl -I https://streamscene.dataandstories.com
   ```

3. **Check API key endpoint:**
   ```bash
   DEVICE_UUID=$(cat /boot/firmware/streamscene-device.txt)
   curl -v "https://streamscene.dataandstories.com/api/devices/$DEVICE_UUID/registration-status"
   ```

#### Common Causes

**A. Server unreachable**

**Solution:**
- Check internet connection
- Verify router allows outbound HTTPS
- Check DNS resolution:
  ```bash
  nslookup streamscene.dataandstories.com
  ```

**B. Incorrect API URL**

**Solution:**
```bash
# Check configured URL
systemctl cat streamscene-client | grep STREAMSCENE_API_URL

# Update if needed
sudo nano /etc/systemd/system/streamscene-client.service
# Edit Environment="STREAMSCENE_API_URL=..."
sudo systemctl daemon-reload
sudo systemctl restart streamscene-client
```

**C. Device not in database**

**Solution:**
- Verify device UUID exists on server
- Check server logs for registration attempts
- Manually add device to database if needed

### 4. Permission Denied Errors

#### Symptoms
- Log shows "Permission denied" errors
- Commands fail with sudo errors
- Hotspot creation fails

#### Diagnostic Steps

1. **Check for permission errors:**
   ```bash
   grep -i "permission denied" /var/log/streamscene/*.log
   ```

2. **Check sudoers file:**
   ```bash
   sudo cat /etc/sudoers.d/streamscene
   ```

3. **Test sudo access:**
   ```bash
   # Try a command that should work without password
   sudo systemctl status hostapd
   # Should NOT prompt for password
   ```

#### Solution

**Install/reinstall sudoers configuration:**

```bash
# Copy sudoers file
sudo cp /home/pi/streamscene-client/../config/sudoers.streamscene /etc/sudoers.d/streamscene

# Set correct permissions (REQUIRED)
sudo chmod 0440 /etc/sudoers.d/streamscene

# Verify syntax
sudo visudo -c

# Restart service
sudo systemctl restart streamscene-client
```

**Verify permissions:**
```bash
# Check file permissions
ls -l /etc/sudoers.d/streamscene
# Should show: -r--r----- 1 root root

# Check sudo rules for pi user
sudo -l -U pi
```

### 5. Service Won't Start

#### Symptoms
- Service shows as "failed" or "inactive"
- Device doesn't boot into hotspot mode
- No log activity

#### Diagnostic Steps

1. **Check service status:**
   ```bash
   sudo systemctl status streamscene-client
   ```

   Look for:
   - Exit code (if failed)
   - Error messages
   - Last log entries

2. **Check systemd journal:**
   ```bash
   sudo journalctl -u streamscene-client -n 50 --no-pager
   ```

3. **Try manual start:**
   ```bash
   cd /home/pi/streamscene-client
   source venv/bin/activate
   python3 main.py
   ```

   Errors will be shown directly.

#### Common Causes

**A. Missing dependencies**

**Solution:**
```bash
# Reinstall Python dependencies
cd /home/pi/streamscene-client
source venv/bin/activate
pip install -r requirements.txt
```

**B. Virtual environment not created**

**Solution:**
```bash
cd /home/pi/streamscene-client
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**C. Missing device UUID**

**Solution:**
```bash
# Check if UUID exists
cat /boot/firmware/streamscene-device.txt

# If missing, create one
python3 -c 'import uuid; print(uuid.uuid4())' | sudo tee /boot/firmware/streamscene-device.txt
sudo chmod 644 /boot/firmware/streamscene-device.txt
```

**D. Import errors**

**Solution:**
```bash
# Check Python path
cd /home/pi/streamscene-client
source venv/bin/activate
python3 -c "import logging_config; import states; import api_client"

# If errors, reinstall
pip install --upgrade -r requirements.txt
```

### 6. Display Issues (E Ink)

#### Symptoms
- Service runs but display stays blank
- Display shows corrupted image
- Python errors related to PIL/display

#### Diagnostic Steps

1. **Check display logs:**
   ```bash
   grep DISPLAY /var/log/streamscene/streamscene-client.log
   ```

2. **Test in headless mode:**
   ```bash
   # Edit service file
   sudo nano /etc/systemd/system/streamscene-client.service

   # Change to:
   Environment="STREAMSCENE_DISPLAY_MODE=headless"

   # Reload and restart
   sudo systemctl daemon-reload
   sudo systemctl restart streamscene-client
   ```

3. **Check E Ink driver:**
   ```bash
   # If using physical E Ink display
   ls /sys/class/gpio/
   lsmod | grep spi
   ```

#### Common Causes

**A. E Ink hardware not connected**

**Solution:**
- Verify physical connection
- Enable SPI interface:
  ```bash
  sudo raspi-config
  # Interface Options -> SPI -> Enable
  sudo reboot
  ```

**B. Missing display driver**

**Solution:**
- Use headless mode until E Ink driver is installed
- Check Waveshare documentation for specific driver

**C. PIL/Pillow errors**

**Solution:**
```bash
cd /home/pi/streamscene-client
source venv/bin/activate
pip install --upgrade pillow
```

## Advanced Troubleshooting

### Enable Debug Logging

Edit `/home/pi/streamscene-client/logging_config.py`:

```python
# Change from INFO to DEBUG
def setup_logger(name: str, log_file: Path, level=logging.DEBUG):  # Changed
```

Restart service:
```bash
sudo systemctl restart streamscene-client
```

### Capture Network Traffic

```bash
# Install tcpdump
sudo apt-get install -y tcpdump

# Capture on wlan0
sudo tcpdump -i wlan0 -w /tmp/capture.pcap

# Analyze with wireshark on desktop
```

### Check System Resources

```bash
# CPU usage
top

# Memory usage
free -h

# Disk space
df -h

# Temperature (if throttling)
vcgencmd measure_temp
```

### Reset to Factory State

```bash
# WARNING: This deletes all device state

# Stop service
sudo systemctl stop streamscene-client

# Remove state files
rm -f ~/streamscene-client/wifi_credentials.json
rm -f ~/streamscene-client/device_state.json
rm -f ~/streamscene-client/device_api_key.txt

# Clear logs
sudo rm -f /var/log/streamscene/*.log

# Restart service
sudo systemctl start streamscene-client
```

### Reinstall From Scratch

```bash
# Backup device UUID
cp /boot/firmware/streamscene-device.txt /tmp/

# Remove client directory
rm -rf ~/streamscene-client

# Re-extract from SD card image or re-deploy
# ... then restore UUID:
sudo cp /tmp/streamscene-device.txt /boot/firmware/

# Start service
sudo systemctl start streamscene-client
```

## Getting Help

### Information to Provide

When asking for help, include:

1. **Device info:**
   ```bash
   cat /etc/os-release
   uname -a
   cat /boot/firmware/streamscene-device.txt
   ```

2. **Service status:**
   ```bash
   sudo systemctl status streamscene-client
   ```

3. **Recent logs:**
   ```bash
   ~/streamscene-client/view_logs.sh recent > /tmp/logs.txt
   ```

4. **Network status:**
   ```bash
   ip addr show wlan0
   iwconfig wlan0
   ```

### Support Channels

- **GitHub Issues:** https://github.com/yourusername/streamscene/issues
- **Documentation:** `docs/` directory
- **Logs:** Always check logs first

## Preventive Maintenance

### Regular Checks

```bash
# Weekly: Check disk space
df -h

# Weekly: Review error logs
~/streamscene-client/view_logs.sh errors

# Monthly: Update system packages
sudo apt-get update && sudo apt-get upgrade -y

# Monthly: Rotate logs manually if needed
sudo logrotate -f /etc/logrotate.d/streamscene
```

### Best Practices

1. **Always check logs first** - 90% of issues are visible in logs
2. **Don't modify core files** - Use environment variables for config
3. **Keep backups** - Save device UUID and credentials
4. **Monitor service** - Set up alerts for service failures
5. **Change default password** - `passwd` immediately after setup

## Quick Reference

### Log Viewer Commands

```bash
~/streamscene-client/view_logs.sh all          # Follow all logs
~/streamscene-client/view_logs.sh errors       # Show errors only
~/streamscene-client/view_logs.sh recent       # Last 100 lines each
~/streamscene-client/view_logs.sh client       # Client log only
~/streamscene-client/view_logs.sh hotspot      # Hotspot log only
~/streamscene-client/view_logs.sh wifi         # WiFi log only
~/streamscene-client/view_logs.sh registration # Registration log only
~/streamscene-client/view_logs.sh systemd      # Systemd journal
~/streamscene-client/view_logs.sh list         # List all log files
~/streamscene-client/view_logs.sh clear        # Clear all logs (confirm)
```

### Service Management

```bash
sudo systemctl start streamscene-client    # Start service
sudo systemctl stop streamscene-client     # Stop service
sudo systemctl restart streamscene-client  # Restart service
sudo systemctl status streamscene-client   # Check status
sudo systemctl enable streamscene-client   # Enable auto-start
sudo systemctl disable streamscene-client  # Disable auto-start
```

### Network Commands

```bash
ip addr show wlan0                 # Show IP address
iwconfig wlan0                     # Show WiFi status
sudo systemctl status hostapd      # Check hotspot daemon
sudo systemctl status dnsmasq      # Check DHCP/DNS daemon
sudo systemctl status wpa_supplicant  # Check WiFi client
```

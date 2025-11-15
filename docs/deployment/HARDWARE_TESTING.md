# StreamScene Hardware Testing Guide

**Created:** November 9, 2025
**Purpose:** Physical setup requirements and testing procedures for StreamScene device deployment

---

## Physical Hardware Checklist

### Minimum Setup (Test on 1 device first)

#### Required Hardware

1. **Raspberry Pi Zero 2 WH** - 1 unit for testing
   - Must have pre-soldered header (WH version)
   - Quad-core ARM Cortex-A53 @ 1GHz
   - 512MB RAM
   - Built-in WiFi and Bluetooth

2. **Waveshare 7.3" 7-color E Ink Display**
   - Model: 7.3inch e-Paper HAT (E) - epd7in3e
   - Resolution: 800×480 pixels
   - 7 colors: Black, White, Red, Yellow, Blue, Green, Orange
   - Connects via GPIO pins

3. **MicroSD Card (64GB)**
   - SanDisk Ultra recommended
   - Class 10, A1, U1
   - For OS and client software

4. **USB Power Supply**
   - 5V, 2.5A minimum (recommend 3A for safety)
   - MicroUSB connector for Pi Zero
   - Reliable power essential for E Ink refresh

5. **MicroSD Card Reader**
   - For your laptop/computer
   - USB-A or USB-C depending on your computer

6. **Ethernet Adapter for Pi Zero** (Optional but helpful)
   - MicroUSB to Ethernet adapter
   - Useful for initial testing without WiFi complications

#### Your Development Computer

1. **SD Card Flashing Tool**
   - Raspberry Pi Imager (recommended): https://www.raspberrypi.com/software/
   - Or Balena Etcher: https://www.balena.io/etcher/

2. **SSH Client**
   - macOS/Linux: Built-in `ssh` command
   - Windows: PuTTY or Windows Terminal with OpenSSH

3. **Serial Console Cable** (Optional but very helpful)
   - USB to TTL Serial Cable
   - For debugging boot issues when display isn't working
   - Connect to GPIO pins 14 (TXD) and 15 (RXD)

---

## Testing Environment Setup

### Network Setup

1. **Test WiFi Network**
   - Know the SSID and password you'll use for testing
   - Should be 2.4GHz network (Pi Zero WiFi doesn't support 5GHz)
   - Stable connection required

2. **Phone or Tablet**
   - To test the captive portal setup flow
   - Must support connecting to WiFi networks
   - Web browser required

3. **Second Computer/Phone**
   - To scan QR codes and register device
   - Needs to be on same network as server

### Server Access

1. **StreamScene Server Accessibility**
   - Server must be accessible from test network
   - If testing locally: both Pi and computer on same network
   - If testing remotely: https://streamscene.dataandstories.com must be reachable

2. **DNS Resolution**
   - Ensure `streamscene.dataandstories.com` resolves correctly
   - Test: `ping streamscene.dataandstories.com`

---

## Step-by-Step Testing Workflow

### Phase 1: Server Testing (No Hardware Needed)

**Duration:** 2-3 hours
**Location:** Your development machine

**Tasks:**
- [ ] Run database migrations
- [ ] Test API endpoints with curl/Postman
- [ ] Test web UI pages in browser
- [ ] Verify QR code generation
- [ ] Test update package upload

**Commands:**
```bash
# Test health endpoint
curl http://localhost:8000/api/health

# Test update check (will fail without device, that's OK)
curl -H "X-Device-Api-Key: test" \
  http://localhost:8000/api/devices/{uuid}/updates/check

# Test web UI
open http://localhost:3000/setup?device=test-uuid
```

**Success Criteria:**
- ✅ All migrations apply cleanly
- ✅ API endpoints return expected responses
- ✅ Web pages render correctly
- ✅ No console errors in browser

---

### Phase 2: Headless Client Testing (No E Ink Needed Yet)

**Duration:** 2-3 hours
**Location:** Raspberry Pi (via SSH)

**Setup Steps:**

1. **Flash SD Card**
   ```bash
   # Download Raspberry Pi OS Lite
   # Flash to SD card using Raspberry Pi Imager
   # Enable SSH in Imager settings
   # Configure WiFi in Imager settings (for initial connection)
   ```

2. **Boot and Connect**
   ```bash
   # Insert SD card into Pi
   # Power on Pi
   # Find Pi IP: sudo nmap -sn 192.168.1.0/24
   # Or check router DHCP leases

   # SSH into Pi
   ssh pi@raspberrypi.local
   # Default password: raspberry
   ```

3. **Install Client Code**
   ```bash
   # Copy code to Pi
   scp -r /root/streamscene/client pi@raspberrypi.local:~/streamscene-client

   # Or use git
   ssh pi@raspberrypi.local
   git clone https://github.com/yourusername/streamscene.git
   cp -r streamscene/client ~/streamscene-client
   ```

4. **Install Dependencies**
   ```bash
   cd ~/streamscene-client
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

5. **Configure Environment**
   ```bash
   # Create .env file
   cat > .env << EOF
   STREAMSCENE_API_URL=http://192.168.1.118:8000
   STREAMSCENE_DEVICE_ID=$(uuidgen)
   STREAMSCENE_API_KEY=test-key-will-be-generated
   STREAMSCENE_DISPLAY_MODE=headless
   EOF
   ```

6. **Test in Headless Mode**
   ```bash
   # Run client
   python -m client.main

   # Check output directory for PNG files
   ls -la client/output/
   ```

**Tasks:**
- [ ] State machine loads and saves state
- [ ] QR code renders to PNG file
- [ ] API client connects to server
- [ ] Headless display saves images
- [ ] All modules import without errors

**Success Criteria:**
- ✅ Client starts without errors
- ✅ PNG files created in `client/output/`
- ✅ State file created and persists
- ✅ Can see QR code in PNG output

---

### Phase 3: WiFi Hotspot Testing (Pi + Laptop, No E Ink Yet)

**Duration:** 3-4 hours
**Location:** Raspberry Pi with laptop

**Prerequisites:**
```bash
# Install required packages
sudo apt-get update
sudo apt-get install -y hostapd dnsmasq network-manager
```

**Setup Steps:**

1. **Test Hotspot Creation**
   ```bash
   # On Pi, run hotspot test
   cd ~/streamscene-client
   source venv/bin/activate

   # Test hotspot module
   python3 << EOF
   from client.setup import hotspot
   ssid = hotspot.generate_ssid("test-uuid-1234")
   print(f"Will create AP: {ssid}")
   hotspot.create_hotspot(ssid)
   EOF
   ```

2. **Connect from Laptop**
   - Look for WiFi network "StreamScene-XXXX"
   - Connect using password "streamscene"
   - Should get IP in 192.168.4.x range

3. **Test Captive Portal**
   ```bash
   # On Pi, start portal server
   sudo python -m client.setup.portal_server

   # On laptop browser:
   # Navigate to http://192.168.4.1
   # Should see WiFi setup form
   ```

4. **Test WiFi Switching**
   ```bash
   # Submit WiFi credentials via form
   # Monitor Pi terminal for connection attempt
   # Verify Pi connects to home WiFi
   # Check Pi gets new IP: ip addr show wlan0
   ```

**Tasks:**
- [ ] Hotspot creates successfully
- [ ] Can connect from laptop
- [ ] Can access 192.168.4.1
- [ ] Form loads correctly (no JavaScript errors would occur anyway)
- [ ] Form submission saves credentials
- [ ] Pi switches to client mode
- [ ] Pi connects to home WiFi

**Success Criteria:**
- ✅ Laptop can connect to Pi hotspot
- ✅ Captive portal loads in browser
- ✅ Form submission works
- ✅ Credentials saved to JSON file
- ✅ Pi successfully connects to home WiFi
- ✅ Can SSH to Pi on new IP

**Common Issues:**
- Hotspot won't start → Check `sudo systemctl status hostapd`
- Can't connect → Verify wlan0 interface: `ip addr show wlan0`
- No DHCP → Check `sudo systemctl status dnsmasq`

---

### Phase 4: E Ink Integration (Full Hardware)

**Duration:** 2-3 hours
**Location:** Pi with E Ink display connected

**Setup Steps:**

1. **Physical Connection**
   ```
   Connect E Ink HAT to Pi GPIO header:
   - Align pins carefully
   - Press down firmly but gently
   - Ensure all 40 pins are seated
   ```

2. **Enable SPI**
   ```bash
   sudo raspi-config
   # Navigate to: Interface Options → SPI → Enable
   sudo reboot
   ```

3. **Verify SPI**
   ```bash
   # After reboot, check SPI devices exist
   ls -l /dev/spidev*
   # Should show: /dev/spidev0.0 and /dev/spidev0.1
   ```

4. **Install Waveshare Library**
   ```bash
   cd ~/streamscene-client
   source venv/bin/activate
   pip install waveshare-epd
   ```

5. **Test Display Driver**
   ```bash
   # Test Waveshare library directly
   python3 << EOF
   from waveshare_epd import epd7in3e
   epd = epd7in3e.EPD()
   epd.init()
   epd.Clear()
   print("Display cleared successfully!")
   epd.sleep()
   EOF
   ```

6. **Enable E Ink Mode**
   ```bash
   # Edit client/display.py
   # Uncomment EInkDisplay class (lines ~120-200)
   # Uncomment return statement in get_display() (line ~221)

   # Update .env
   echo "STREAMSCENE_DISPLAY_MODE=eink" >> .env
   ```

7. **Test Full Setup Flow**
   ```bash
   # Run client with E Ink
   sudo python -m client.main
   # (sudo required for GPIO access)
   ```

**Tasks:**
- [ ] SPI interface enabled
- [ ] E Ink library installed
- [ ] Display clears successfully
- [ ] QR code appears on screen (scannable)
- [ ] WiFi setup instructions readable
- [ ] State transitions show correct screens
- [ ] Content displays correctly

**Success Criteria:**
- ✅ Display initializes without errors
- ✅ Can see WiFi setup instructions on screen
- ✅ QR code is sharp and scannable
- ✅ Screen refreshes (~30 seconds)
- ✅ All text is legible
- ✅ Colors render correctly (7-color palette: Black, White, Red, Yellow, Blue, Green, Orange)

**Common Issues:**
- Display not responding → Check GPIO connection
- SPI errors → Verify SPI enabled: `lsmod | grep spi`
- Waveshare library import fails → Reinstall: `pip install --force-reinstall waveshare-epd`
- Permission errors → Use `sudo` for GPIO access

---

### Phase 5: OTA Update Testing

**Duration:** 1-2 hours
**Location:** Pi with full setup

**Setup Steps:**

1. **Create Test Update Package**
   ```bash
   # On development machine
   cd /root/streamscene

   # Create update package
   mkdir -p /tmp/update-v1.1.0

   # Copy updated client code
   cp -r client /tmp/update-v1.1.0/

   # Create manifest
   cat > /tmp/update-v1.1.0/manifest.json << EOF
   {
     "version": "1.1.0",
     "min_version": "1.0.0",
     "checksum": "will-be-calculated",
     "release_date": "2025-11-09",
     "changelog": "Test update"
   }
   EOF

   # Create install script
   cat > /tmp/update-v1.1.0/install.sh << 'EOF'
   #!/bin/bash
   set -e

   echo "Installing update v1.1.0..."

   # Stop service
   sudo systemctl stop streamscene-client || true

   # Install dependencies
   pip install -r requirements.txt

   # Copy files
   cp -r client/* /home/pi/streamscene-client/

   # Restart service
   sudo systemctl start streamscene-client

   echo "Update installed successfully"
   EOF

   chmod +x /tmp/update-v1.1.0/install.sh

   # Create tarball
   cd /tmp
   tar -czf update-v1.1.0.tar.gz update-v1.1.0/
   ```

2. **Upload to Server**
   ```bash
   # Copy to server update directory
   sudo cp /tmp/update-v1.1.0.tar.gz /var/lib/streamscene/updates/

   # Or use web UI to upload
   ```

3. **Trigger Update**
   ```bash
   # Via web UI: Click "Trigger Update" for device

   # Or via API:
   curl -X POST http://localhost:8000/api/admin/updates/trigger/{device_id}
   ```

4. **Monitor Update Process**
   ```bash
   # On Pi, watch logs
   sudo journalctl -u streamscene-client -f

   # Or watch state file
   watch -n 1 cat /home/pi/streamscene-client/device_state.json
   ```

**Tasks:**
- [ ] Update package created
- [ ] Upload to server succeeds
- [ ] Device detects update
- [ ] Download completes
- [ ] Checksum verification passes
- [ ] Installation executes
- [ ] Device reboots
- [ ] New version running
- [ ] Server receives confirmation

**Success Criteria:**
- ✅ Update downloads without errors
- ✅ Checksum matches
- ✅ Installation script runs
- ✅ Device reboots automatically
- ✅ Device comes back online
- ✅ Version updated in database
- ✅ No data loss

---

## Recommended Testing Order

### Day 1: Server-Side Development + Testing

**Morning (3-4 hours):**
- ✅ Database migrations
- ✅ API endpoint implementation
- ✅ Test with curl/Postman

**Afternoon (3-4 hours):**
- ✅ Web UI pages
- ✅ QR code generation
- ✅ End-to-end server testing

**Deliverables:**
- Working API endpoints
- Functional web pages
- QR codes generating correctly

---

### Day 2: Client Development (Headless Mode)

**Morning (3-4 hours):**
- ✅ State machine implementation
- ✅ WiFi hotspot setup
- ✅ Test on Pi (headless mode)

**Afternoon (3-4 hours):**
- ✅ Captive portal server
- ✅ WiFi switching logic
- ✅ Registration flow
- ✅ Verify all PNG outputs

**Deliverables:**
- State machine working
- WiFi setup functional (tested with laptop)
- Registration flow tested (headless)

---

### Day 3: Hardware Integration

**Morning (2-3 hours):**
- ✅ Connect E Ink display
- ✅ Test display driver
- ✅ Enable E Ink mode
- ✅ Run full setup flow

**Afternoon (2-3 hours):**
- ✅ OTA update system
- ✅ Create and install test update
- ✅ Verify reboot and recovery

**Evening (1 hour):**
- ✅ Bug fixes
- ✅ Polish and refinements

**Deliverables:**
- Fully working prototype device
- Complete setup flow validated
- OTA update tested

---

### Day 4: Polish and Build Additional Units

**Tasks:**
- ✅ Fix any issues from Day 3
- ✅ Create base SD card image
- ✅ Clone to 2 more SD cards
- ✅ Test each device individually
- ✅ Label devices with UUIDs
- ✅ Create QR code stickers

**Deliverables:**
- 3 working devices
- Documented issues and solutions
- Ready to ship

---

## Physical Workspace Needs

### Desk Space Requirements

**Layout:**
```
┌─────────────────────────────────────────┐
│  Laptop (development)                   │
│  ┌──────────────────┐                   │
│  │                  │                   │
│  └──────────────────┘                   │
│                                          │
│  Raspberry Pi + E Ink Display           │
│  ┌─────────────────┐                    │
│  │   800x480       │                    │
│  │   E Ink         │                    │
│  │   Display       │                    │
│  └─────────────────┘                    │
│     ║                                    │
│  [Pi Zero]                              │
│     │                                    │
│  [Power Supply]                         │
│                                          │
│  Phone (for QR scanning)                │
│  SD cards and tools                     │
│                                          │
└─────────────────────────────────────────┘
```

**You Need:**
1. Desk space for:
   - Laptop
   - Raspberry Pi with E Ink (takes ~8" × 5" space)
   - Phone for testing QR codes
   - SD cards and tools

2. Power strips:
   - Laptop charger
   - Pi power supply
   - Optional: extra USB ports for serial cable

3. Labels/markers:
   - Label each SD card with device UUID
   - Track which device is which

4. Anti-static mat (optional):
   - Protects Pi boards during handling

---

## Optional but Helpful Tools

### Debugging Tools

1. **Serial Debug Cable** ($10-15)
   - See boot messages if display isn't working
   - Connect to GPIO pins 14 (TXD) and 15 (RXD)
   - Essential if you can't SSH in

2. **HDMI Adapter for Pi Zero** ($5-10)
   - MicroHDMI to HDMI adapter
   - For troubleshooting (won't be used in production)
   - Helpful if WiFi setup fails

3. **USB Keyboard/Mouse for Pi** (if you have spare)
   - MicroUSB OTG adapter needed
   - For manual debugging if network is down

### Measurement Tools

1. **Multimeter** (optional)
   - Verify power supply voltage (should be 5V ±5%)
   - Check GPIO pin voltages if needed

2. **USB Power Monitor** (optional)
   - Measure current draw
   - Verify power supply is adequate
   - Pi Zero + E Ink can draw 400-800mA during refresh

### Backup Equipment

1. **Spare SD Cards**
   - For backups and testing different configurations
   - Recommended: 2-3 extra cards

2. **SD Card Duplicator** (optional)
   - If building many devices
   - Faster than flashing each card individually

---

## Pre-Testing Checklist

### Before You Start Coding

- [ ] Raspberry Pi OS image downloaded
- [ ] E Ink display drivers available (Waveshare library)
- [ ] Test WiFi network credentials known
- [ ] Server running and accessible
- [ ] SSH keys set up for Pi access
- [ ] Serial console cable tested (if using)
- [ ] Backup of current working codebase

### Before Day 2 (WiFi Testing)

- [ ] Understand how to SSH into Pi
- [ ] Can access Pi on local network
- [ ] Phone can connect to unknown WiFi networks
- [ ] Know how to reset Pi for repeated setup tests
- [ ] `hostapd` and `dnsmasq` packages installed

### Before Day 3 (E Ink Testing)

- [ ] SPI enabled on Pi (`sudo raspi-config`)
- [ ] E Ink library installed (`pip install waveshare-epd`)
- [ ] Test display with Waveshare sample code
- [ ] GPIO pins properly connected (verify pinout)
- [ ] Confirmed display model matches code (7.3" E variant - 7-color epd7in3e)

---

## Common Issues and Solutions

### Issue: Pi Won't Boot

**Symptoms:** No lights, no activity

**Solutions:**
1. Check power supply (should be 5V, 2.5A minimum)
2. Verify SD card is properly inserted
3. Try different power supply
4. Check SD card boot flag is set
5. Re-flash SD card

---

### Issue: Can't SSH into Pi

**Symptoms:** Connection refused or timeout

**Solutions:**
1. Verify SSH enabled in Raspberry Pi Imager
2. Check Pi is on network: `ping raspberrypi.local`
3. Find Pi IP: `sudo nmap -sn 192.168.1.0/24`
4. Check router DHCP leases
5. Connect via serial console cable
6. Use HDMI to troubleshoot network

---

### Issue: E Ink Display Not Working

**Symptoms:** Black screen, no response

**Solutions:**
1. Verify SPI enabled: `lsmod | grep spi`
2. Check `/dev/spidev*` exists
3. Verify GPIO connection (all 40 pins seated)
4. Test with Waveshare sample code
5. Check power supply is adequate
6. Ensure running with `sudo` (GPIO access)

---

### Issue: Hotspot Won't Create

**Symptoms:** `hostapd` fails to start

**Solutions:**
1. Check `sudo systemctl status hostapd`
2. Review config: `cat /etc/hostapd/hostapd.conf`
3. Verify wlan0 interface exists: `ip link show wlan0`
4. Check for conflicting network managers
5. Review logs: `sudo journalctl -u hostapd -n 50`

---

### Issue: WiFi Won't Connect

**Symptoms:** Can't connect to home WiFi

**Solutions:**
1. Verify credentials are correct
2. Check 2.4GHz network (Pi Zero doesn't support 5GHz)
3. Try manual connection: `nmcli dev wifi connect "SSID" password "PASS"`
4. Check signal strength: `iwlist wlan0 scan | grep SSID`
5. Reboot Pi and try again

---

### Issue: Update Download Fails

**Symptoms:** Update errors or timeout

**Solutions:**
1. Verify server is accessible from Pi
2. Check update package exists on server
3. Verify Nginx serving `/updates/` directory
4. Check disk space: `df -h`
5. Try manual download: `curl -O http://server/updates/package.tar.gz`

---

## Testing Safety

### Protect Your Hardware

1. **Always handle Pi when powered off** (except testing)
2. **Use ESD-safe practices** (touch grounded metal before handling)
3. **Don't force connections** (GPIO pins are delicate)
4. **Verify polarity** before connecting power
5. **Don't hot-swap E Ink display** (can damage it)

### Protect Your Data

1. **Backup SD cards** before major changes
2. **Version control** all code changes
3. **Document working configurations**
4. **Keep test database separate** from production
5. **Have rollback plan** for updates

---

## Success Metrics

### You're Ready to Ship When:

- [ ] Device boots automatically
- [ ] WiFi setup works reliably (>90% success rate)
- [ ] QR code is scannable
- [ ] Registration completes successfully
- [ ] Updates download and install correctly
- [ ] Device recovers from errors gracefully
- [ ] E Ink display shows clear, readable content
- [ ] Tested with 3 different WiFi networks
- [ ] Tested multiple setup/reset cycles
- [ ] Documented all issues and workarounds

---

## Final Notes

### Testing Philosophy

**Test incrementally:**
- Don't skip phases
- Validate each component before integration
- Keep detailed notes of failures

**Test realistically:**
- Use actual WiFi networks
- Test with real phones for QR scanning
- Simulate user mistakes (wrong password, etc.)

**Test completely:**
- Happy path (everything works)
- Error paths (WiFi fails, update fails, etc.)
- Edge cases (weak signal, slow internet, etc.)

### When to Ask for Help

1. **Hardware issues** → Check Raspberry Pi forums
2. **E Ink issues** → Waveshare wiki and support
3. **WiFi issues** → Raspberry Pi network documentation
4. **Software bugs** → Debug with serial console first

---

**Good luck with your build!** 🎉

*Remember: Test on 1 device completely before building the rest.*

---

**Last Updated:** November 9, 2025

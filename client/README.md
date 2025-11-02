# StreamScene E Ink Client

Python client for Raspberry Pi Zero 2 WH devices with Waveshare 7.3" 6-color E Ink displays.

Supports two modes:
- **Headless mode** (testing): Saves PNG files - no hardware needed
- **E Ink mode** (production): Displays on actual E Ink screen

## Quick Start (Testing Mode)

### 1. Install Dependencies

```bash
# From project root
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file or export variables:

```bash
export STREAMSCENE_API_URL="http://localhost:8000"
export STREAMSCENE_DEVICE_ID="your-device-uuid-here"
export STREAMSCENE_API_KEY="your-api-key-here"
```

### 3. Run Client

```bash
cd /root/streamscene
python -m client.main
```

The client will:
- Connect to the API
- Fetch content every 60 seconds
- Save rendered images to `client/output/`
- Check `client/output/latest.png` to see current display

### 4. Test Individual Components

```bash
# Test configuration
python -m client.config

# Test API client
python -m client.api_client

# Test renderer
python -m client.renderer
```

---

## Hardware Mode (Raspberry Pi + E Ink)

### Prerequisites

- Raspberry Pi Zero 2 WH
- Waveshare 7.3inch e-Paper HAT (F) - 6-color
- SD card with Raspberry Pi OS Lite
- Power supply (5V 2.5A recommended)

### Hardware Setup

1. **Assemble Hardware**
   - Connect E Ink HAT to Pi's 40-pin GPIO header
   - Ensure all pins are seated properly

2. **Enable SPI**
   ```bash
   sudo raspi-config
   # Navigate to: Interface Options → SPI → Enable
   sudo reboot
   ```

3. **Install System Dependencies**
   ```bash
   sudo apt update
   sudo apt install -y python3-pip python3-pil python3-numpy git
   sudo apt install -y libopenjp2-7 libtiff5
   ```

4. **Install Waveshare Library**
   ```bash
   pip3 install waveshare-epd
   ```

### Code Changes for Hardware

**Only 2 changes needed:**

1. **Edit `client/display.py`:**
   - Find the commented section: "UNCOMMENT THIS SECTION"
   - Uncomment the `EInkDisplay` class (lines ~100-160)
   - Uncomment the `return EInkDisplay()` line in `get_display()`

2. **Update environment variable:**
   ```bash
   export STREAMSCENE_DISPLAY_MODE="eink"
   ```

That's it! Everything else stays the same.

### Deploy to Raspberry Pi

1. **Copy Code to Pi**
   ```bash
   # From your development machine
   scp -r /root/streamscene pi@raspberrypi.local:~/
   ```

2. **Configure on Pi**
   ```bash
   ssh pi@raspberrypi.local
   cd ~/streamscene

   # Create .env file
   cat > .env << EOF
   STREAMSCENE_API_URL="http://your-server-ip:8000"
   STREAMSCENE_DEVICE_ID="your-device-uuid"
   STREAMSCENE_API_KEY="your-api-key"
   STREAMSCENE_DISPLAY_MODE="eink"
   EOF
   ```

3. **Install Dependencies**
   ```bash
   pip3 install -r requirements.txt
   pip3 install waveshare-epd
   ```

4. **Test Run**
   ```bash
   sudo python3 -m client.main
   # sudo required for GPIO access
   ```

### Set Up Auto-Start (systemd)

Create `/etc/systemd/system/streamscene.service`:

```ini
[Unit]
Description=StreamScene E Ink Client
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/streamscene
EnvironmentFile=/home/pi/streamscene/.env
ExecStart=/usr/bin/python3 -m client.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable streamscene
sudo systemctl start streamscene

# Check status
sudo systemctl status streamscene

# View logs
sudo journalctl -u streamscene -f
```

---

## Configuration Options

All configuration via environment variables:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `STREAMSCENE_API_URL` | Yes | http://localhost:8000 | API server URL |
| `STREAMSCENE_DEVICE_ID` | Yes | - | Device UUID |
| `STREAMSCENE_API_KEY` | Yes | - | Device API key |
| `STREAMSCENE_DISPLAY_MODE` | No | headless | Display mode: "headless" or "eink" |
| `STREAMSCENE_POLL_INTERVAL` | No | 60 | Content fetch interval (seconds) |
| `STREAMSCENE_HEARTBEAT_INTERVAL` | No | 300 | Heartbeat interval (seconds) |
| `STREAMSCENE_REQUEST_TIMEOUT` | No | 10 | API request timeout (seconds) |
| `STREAMSCENE_MAX_RETRIES` | No | 3 | Max API retry attempts |

---

## Troubleshooting

### Client Won't Start

**Check configuration:**
```bash
python -m client.config
```

**Common issues:**
- Missing `DEVICE_ID` or `API_KEY`
- API server not running
- Network connectivity issues

### Can't Connect to API

**Test API directly:**
```bash
curl http://your-server:8000/api/health
```

**Check client logs:**
```bash
sudo journalctl -u streamscene -n 50
```

### E Ink Display Not Working

**Verify SPI is enabled:**
```bash
ls /dev/spidev*
# Should show: /dev/spidev0.0 and /dev/spidev0.1
```

**Test Waveshare library:**
```python
from waveshare_epd import epd7in3f
epd = epd7in3f.EPD()
epd.init()
epd.Clear()
```

**Run with sudo:**
```bash
sudo python3 -m client.main
```

### Display Shows Wrong Colors

The 6-color E Ink palette is:
- Black (0, 0, 0)
- White (255, 255, 255)
- Red (255, 0, 0)
- Yellow (255, 255, 0)
- Blue (0, 0, 255)
- Green (0, 255, 0)

Colors are dithered using Floyd-Steinberg algorithm.

### Display Updates Too Slowly

E Ink refresh takes ~30 seconds. This is normal!

Don't set `POLL_INTERVAL` below 60 seconds or the display won't keep up.

---

## Development

### Running Tests

```bash
# From project root
pytest client/tests/
```

### Code Structure

```
client/
├── __init__.py           # Package init
├── config.py            # Configuration
├── display.py           # Display adapters (headless + E Ink)
├── api_client.py        # API communication
├── renderer.py          # Content rendering
├── main.py              # Main client loop
├── output/              # PNG output (headless mode)
├── tests/               # Unit tests
└── README.md            # This file
```

### Adding Features

To add new content types:

1. Update `renderer.py` to handle the new type
2. Test in headless mode first
3. Deploy to Pi when working

---

## Hardware Specifications

**Waveshare 7.3inch e-Paper HAT (F)**
- Resolution: 800x480 pixels
- Colors: 6 colors (Black, White, Red, Yellow, Blue, Green)
- Refresh time: ~30 seconds (full update)
- Interface: SPI
- Power: 3.3V

**Raspberry Pi Zero 2 WH**
- CPU: Quad-core ARM Cortex-A53 @ 1GHz
- RAM: 512MB
- Wireless: 802.11 b/g/n
- Bluetooth: 4.2 / BLE
- GPIO: 40-pin header (pre-soldered)

---

## FAQ

**Q: Can I use a different Raspberry Pi model?**
A: Yes! Pi 3, Pi 4, Pi Zero W all work. Pi Zero 2 WH is recommended for power efficiency.

**Q: Can I use a different E Ink display?**
A: Yes, but you'll need to modify `display.py` to use the appropriate Waveshare library for your model.

**Q: How much power does it use?**
A: Pi Zero 2 WH: ~100-200mA idle, ~400mA during refresh. Use a 2.5A power supply.

**Q: Can multiple devices share an API key?**
A: No! Each device must have its own unique API key for security.

**Q: What if my network goes down?**
A: The client retries with exponential backoff and displays an error message. It will reconnect automatically.

**Q: Can I manually trigger a refresh?**
A: Yes! Send SIGUSR1: `sudo kill -SIGUSR1 $(pgrep -f client.main)`

---

## Support

For issues or questions:
1. Check logs: `sudo journalctl -u streamscene -f`
2. Test components individually (see "Test Individual Components" above)
3. Review troubleshooting section
4. Check API server logs

---

## License

Part of the StreamScene project. See main repository for license information.

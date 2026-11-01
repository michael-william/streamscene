# StreamScene SD Card Image Guide

> **This is the image reference.** For the end-to-end process of producing and
> handing out a device - including what the recipient does - follow
> [DISTRIBUTION.md](DISTRIBUTION.md). This document covers what is inside the
> image and how to work with it.

## Overview

The StreamScene SD card image is a pre-configured Raspberry Pi OS image with all client software, dependencies, and configurations pre-installed. Simply flash to an SD card, insert into a Raspberry Pi Zero 2 WH, and power on.

The base is **Raspberry Pi OS Lite Bookworm, 32-bit (armhf)**, pinned to a
specific snapshot in `build_sd_image.sh`. The boot partition is mounted at
`/boot/firmware` (Bookworm layout), which is where `streamscene-device.txt`
lives - not `/boot`.

## Building the Image

### Prerequisites

- Debian/Ubuntu Linux system (for chroot support)
- Root access (`sudo`)
- At least 8GB free disk space
- Internet connection

### Required Packages

```bash
sudo apt-get install -y \
    wget \
    xz-utils \
    parted \
    dosfstools \
    qemu-user-static \
    losetup
```

### Build Process

> **The build must run on the Proxmox host, not in CT118.** CT118 has the
> required tools but no `/dev/loop*` devices, so it cannot loop-mount the
> image. macOS cannot build at all (no loop devices, no ext4, no foreign-arch
> chroot). See DISTRIBUTION.md for staging a clean build tree.

1. **Navigate to the build tree** (staged from CT118, *not* the stale
   `/root/streamscene` checkout on the host):
   ```bash
   cd /root/streamscene-build
   ```

2. **Run build script:**
   ```bash
   sudo ./build_sd_image.sh
   ```

3. **Wait for completion** (roughly 3-6 minutes on the host; longer on a
   slow connection, since the base image is downloaded once)

4. **Output:**
   - Image file: `streamscene-client-<version>.img`
   - Checksum: `streamscene-client-<version>.img.sha256`

5. **Confirm it verified.** A good build ends with
   `image verification passed`. The build aborts rather than emit a broken
   image; anything else means do not flash the output.

### What the Build Script Does

1. Downloads Raspberry Pi OS Lite Bookworm (armhf, pinned snapshot)
2. Mounts image and configures system:
   - Enables SSH (boot flag file **and** systemd symlink)
   - Sets default password (`pi` / `streamscene`)
   - Configures mDNS (`streamscene.local`)
   - **Enables SPI** (`dtparam=spi=on`) - required by the Waveshare HAT
   - **Deliberately does not write a device UUID** (see below)
3. Installs dependencies via chroot:
   - `hostapd` - WiFi access point
   - `dnsmasq` - DHCP/DNS server
   - `python3-venv` - Virtual environment support
4. Copies StreamScene client code to `/home/pi/streamscene-client`,
   including the vendored `waveshare_epd/` display driver, and builds the venv
5. Installs system configurations:
   - Sudoers file (passwordless network commands)
   - Logrotate configuration
6. Installs systemd services:
   - `streamscene-client.service` - Main client service, with the dev-only
     `STREAMSCENE_ALLOW_ETHERNET` flag stripped from the shipped copy
   - `streamscene-firstboot.service` - First-boot provisioning
7. **Verifies the image** with `scripts/verify_image.py`, run inside the image
   using its own venv - aborts the build on any failure
8. Creates final image with SHA256 checksum

### Why no UUID is written at build time

A UUID written during the build is baked into the image, so **every card
flashed from it would claim the same device identity** on the server. The
image therefore ships with no `streamscene-device.txt`;
`streamscene-firstboot.service` generates a unique one on each device's first
boot. Do not reinstate a build-time UUID.

For the same reason, never clone a card that has already booted - clone from
the original `.img`.

### The display driver is vendored, not installed

`waveshare-epd` **is not on PyPI**. Listing it in `client/requirements.txt`
makes pip abort the entire transaction, which silently leaves the venv with no
pillow, requests or qrcode either - and the build used to report success
anyway. The driver is copied into the repo at `client/waveshare_epd/` instead;
see that directory's `VENDOR.md` for provenance and update procedure.

Note that `waveshare_epd/epdconfig.py` performs platform detection at *import*
time by grepping `/proc/cpuinfo` for "Raspberry". It can therefore only be
imported on real Pi hardware - never in the build chroot, and not on the
Proxmox host. The build verifies the driver statically instead.

## Flashing the Image

### Linux

```bash
# Find SD card device (e.g., /dev/sdb)
lsblk

# Flash image
sudo dd if=streamscene-client-1.0.0.img of=/dev/sdX bs=4M status=progress

# Sync to ensure writes complete
sync
```

### macOS

```bash
# Find SD card device
diskutil list

# Unmount (but don't eject)
diskutil unmountDisk /dev/diskX

# Flash image
sudo dd if=streamscene-client-1.0.0.img of=/dev/rdiskX bs=1m

# Eject
diskutil eject /dev/diskX
```

### Windows

Use one of these tools:
- [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
- [Etcher](https://www.balena.io/etcher/)

## First Boot Sequence

### Automatic Provisioning

On first boot, the device automatically:

1. **Generates unique UUID** - Written to `/boot/firmware/streamscene-device.txt`
2. **Creates log directory** - `/var/log/streamscene` with correct permissions
3. **Enables StreamScene client service** - Auto-starts on future boots
4. **Starts client service** - Begins WiFi setup flow
5. **Self-deletes provisioning service** - Runs only once

Logs: `/var/log/streamscene-firstboot.log`

### Expected Boot Timeline

| Time | Event | What Happens |
|------|-------|--------------|
| 0:00 | Power on | Raspberry Pi boots |
| 0:30 | First boot script runs | UUID generated, service enabled |
| 0:45 | Client service starts | Checks for WiFi credentials |
| 1:00 | **Hotspot activates** | `StreamScene-XXXX` network appears |
| 1:15 | Ready for setup | Portal at http://192.168.4.1 |

## WiFi Setup Flow

### 1. Connect to Hotspot

- **SSID:** `StreamScene-XXXX` (last 4 chars of UUID)
- **Password:** `streamscene`
- **Hotspot IP:** `192.168.4.1`

### 2. Captive Portal

- Opens automatically on most devices
- Manual access: http://192.168.4.1
- Enter home WiFi credentials
- Click "Connect"

### 3. Device Connects

- Hotspot stops
- Device connects to home WiFi
- Gets IP via DHCP
- Accessible via SSH: `ssh pi@streamscene.local` or `ssh pi@<IP>`

## Device Registration

### 1. QR Code Display

After WiFi connection, device displays QR code on E Ink screen.

### 2. Scan with Phone

1. Open camera app
2. Point at QR code
3. Tap notification to open registration URL

### 3. Web Registration

1. Log in to StreamScene web app
2. Choose device nickname
3. Click "Register"
4. Device receives API key
5. Enters normal operation mode

## SSH Access

### Default Credentials

- **Username:** `pi`
- **Password:** `streamscene`

**⚠️ IMPORTANT:** Change default password after first login:
```bash
passwd
```

### Access Methods

1. **Via mDNS (recommended):**
   ```bash
   ssh pi@streamscene.local
   ```

2. **Via IP address:**
   ```bash
   # Find IP from router DHCP table or:
   nmap -sn 192.168.1.0/24 | grep streamscene

   ssh pi@192.168.1.XXX
   ```

3. **Via hotspot mode (during setup):**
   ```bash
   ssh pi@192.168.4.1
   ```

## Troubleshooting

### Hotspot Not Appearing

1. **Check service status:**
   ```bash
   ssh pi@streamscene.local
   sudo systemctl status streamscene-client
   ```

2. **View logs:**
   ```bash
   ~/streamscene-client/view_logs.sh all
   ```

3. **Check first boot log:**
   ```bash
   cat /var/log/streamscene-firstboot.log
   ```

### Can't SSH to Device

1. **Verify SSH is enabled:**
   - Mount SD card on computer
   - Check for `/boot/ssh` file (should exist)

2. **Check device is powered:**
   - Green LED should blink (disk activity)
   - Allow 60-90 seconds for first boot

3. **Try different network:**
   - Some routers block mDNS
   - Find IP in router admin panel

### WiFi Connection Fails

1. **Check credentials:**
   - SSID is case-sensitive
   - Password must be exact

2. **Check WiFi frequency:**
   - Pi Zero 2 WH supports 2.4GHz only
   - 5GHz networks won't appear

3. **Restart WiFi setup:**
   ```bash
   ssh pi@192.168.4.1
   rm ~/streamscene-client/wifi_credentials.json
   rm ~/streamscene-client/device_state.json
   sudo systemctl restart streamscene-client
   ```

### Registration Timeout

1. **Check internet connection:**
   ```bash
   ping -c 3 streamscene.dataandstories.com
   ```

2. **Verify API URL:**
   ```bash
   systemctl cat streamscene-client | grep STREAMSCENE_API_URL
   ```

3. **Check server is reachable:**
   ```bash
   curl -I https://streamscene.dataandstories.com
   ```

## Advanced Configuration

### Change API Server

Edit `/etc/systemd/system/streamscene-client.service`:

```ini
Environment="STREAMSCENE_API_URL=https://your-server.com"
```

Reload and restart:
```bash
sudo systemctl daemon-reload
sudo systemctl restart streamscene-client
```

### Enable Headless Mode (no E Ink)

Edit `/etc/systemd/system/streamscene-client.service`:

```ini
Environment="STREAMSCENE_DISPLAY_MODE=headless"
```

### View Live Logs

```bash
# All logs
~/streamscene-client/view_logs.sh all

# Just errors
~/streamscene-client/view_logs.sh errors

# Systemd journal
sudo journalctl -u streamscene-client -f
```

### Reset Device to Factory

```bash
# Remove all state and credentials
rm -f ~/streamscene-client/wifi_credentials.json
rm -f ~/streamscene-client/device_state.json
rm -f ~/streamscene-client/device_api_key.txt

# Clear logs
sudo rm -f /var/log/streamscene/*.log

# Restart service
sudo systemctl restart streamscene-client
```

## Security Notes

### Default Password

The image ships with default credentials (`pi` / `streamscene`). This is acceptable for initial setup but **MUST BE CHANGED** for production deployment:

```bash
passwd
```

### SSH Key Authentication (Recommended)

1. **Generate SSH key on your computer:**
   ```bash
   ssh-keygen -t ed25519
   ```

2. **Copy to device:**
   ```bash
   ssh-copy-id pi@streamscene.local
   ```

3. **Disable password authentication (optional):**
   ```bash
   sudo nano /etc/ssh/sshd_config
   # Set: PasswordAuthentication no
   sudo systemctl restart ssh
   ```

### Network Security

- Device creates WPA2 hotspot (password: `streamscene`)
- Consider changing hotspot password for production
- WiFi credentials stored in plain text (local file only)
- API keys hashed with bcrypt on server

## Image Customization

### Pre-Configure WiFi

Before flashing, mount image and edit:

`/home/pi/streamscene-client/wifi_credentials.json`:
```json
{
  "ssid": "Your-Network",
  "password": "your-password",
  "configured": true
}
```

Device will skip hotspot and connect directly.

### Change Default Hotspot Password

Edit `client/setup/hotspot.py` before building:

```python
def create_hostapd_config(ssid: str, password: str = "YOUR_PASSWORD"):
    if len(password) < 8:
        password = "YOUR_PASSWORD"  # Fallback
```

### Add Custom Startup Scripts

Place scripts in `/home/pi/streamscene-client/` and make executable.

Add to `/etc/rc.local` (before `exit 0`):
```bash
/home/pi/streamscene-client/your-script.sh &
```

## Distribution

### Compress Image

```bash
# Create compressed image
xz -9 -T 0 streamscene-client-1.0.0.img

# Result: streamscene-client-1.0.0.img.xz (~500MB vs ~2GB)
```

### Verify Checksum

```bash
sha256sum -c streamscene-client-1.0.0.img.sha256
```

### Upload for Distribution

- GitHub Releases (preferred)
- Google Drive
- Dropbox
- Self-hosted server

Include SHA256 checksum for verification.

## Support

For issues or questions:
- **Logs:** `~/streamscene-client/view_logs.sh all`
- **Service status:** `sudo systemctl status streamscene-client`
- **System logs:** `sudo journalctl -xe`
- **GitHub Issues:** https://github.com/yourusername/streamscene/issues

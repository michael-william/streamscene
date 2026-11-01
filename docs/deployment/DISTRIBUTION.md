# StreamScene Distribution Guide

**Audience:** you, building and handing out devices.
**For the recipient's own instructions, see [Part 3](#part-3--what-the-recipient-does).**

This is the authoritative process for producing a StreamScene device for
somebody else. It is not a development guide - see the
[environment map](#environments) below for which doc covers what.

---

## Environments

Three different setups exist and have historically been confused with each
other. Know which one you are in before following any doc:

| # | Environment | Network | Purpose | Doc |
|---|---|---|---|---|
| A | Local dev | Pi on USB-ethernet adapter, home LAN | Bench work, SSH always available | `WIFI_SETUP.md` |
| B | Remote debug | Pi over USB to a helper's Mac | Iterating on hardware you cannot touch | `../development/REMOTE_DEBUG.md` |
| C | **Distribution** | Flash image → hotspot → captive portal → QR | What recipients do | **this doc** |

Environment A's instructions will not produce a distributable device: they
install packages by hand and rely on ethernet, which shipped devices do not
have.

---

## Part 1 - Build the image

### Where the build must run

**On the Proxmox host.** Not in CT118, and not on a Mac.

| Machine | Can build? | Why |
|---|---|---|
| Proxmox host | **Yes** | Has `/dev/loop*` plus every required tool |
| CT118 | No | Has the tools but **no loop devices** - cannot loop-mount the image |
| macOS | No | No loop devices, no ext4, no foreign-arch chroot |

CT118 remains the source of truth for *code*. The host is only a build
environment, fed from CT118.

> **Do not build from `/root/streamscene` on the host.** That is a stale
> second checkout. Stage a fresh tree as below.

### Stage the build tree

Only four paths are needed:

```bash
sudo mkdir -p /root/streamscene-build
sudo pct exec 118 -- tar -C /root/streamscene -cf - \
    --exclude='__pycache__' --exclude='*.bak-preclaude' \
    build_sd_image.sh client config scripts \
  | sudo tar -C /root/streamscene-build -xf -
```

> When running `pct exec` from a script or agent, **pipe its output**
> (`| cat` at minimum). Unpiped, it clobbers the caller's output capture.

### Build

```bash
cd /root/streamscene-build
sudo ./build_sd_image.sh
```

Takes roughly 3-6 minutes on the host and needs ~8 GB free. Output:

- `streamscene-client-<version>.img` (~2.4 GB)
- `streamscene-client-<version>.img.sha256`

### What the build guarantees

The build **aborts** rather than shipping a broken image. `scripts/verify_image.py`
runs inside the image using its own venv and checks:

| Check | Proves |
|---|---|
| `venv OK` | pillow / requests / qrcode import |
| `gpio OK` | spidev / gpiozero / lgpio import |
| `driver OK` | vendored `waveshare_epd` present, compiles, panel is 800x480 |
| `client OK` | `main.py` compiles |

A successful build prints `image verification passed`. Anything else is a
failed build - do not flash the output.

### Never hand-edit the image

Editing the `.img` after the build invalidates its checksum and makes the build
irreproducible. If something needs to change, change `build_sd_image.sh` and
rebuild. Always confirm before distributing:

```bash
sha256sum -c streamscene-client-<version>.img.sha256
```

---

## Part 2 - Flash the card

Compress first if sending it anywhere (~2.4 GB → ~500 MB):

```bash
xz -9 -T 0 -k streamscene-client-<version>.img
sha256sum streamscene-client-<version>.img.xz > streamscene-client-<version>.img.xz.sha256
```

### Raspberry Pi Imager

1. **Choose OS → Use custom** → select the `.img` or `.img.xz`
2. **Do not pick an OS from the list.** That flashes stock Raspberry Pi OS,
   which contains none of the StreamScene client. A device flashed this way
   does nothing at all - no hotspot, no QR code.
3. **Leave the gear-icon OS customisation OFF.** It overwrites the image's
   own user, SSH and network configuration.

### Command line

```bash
# macOS
diskutil list
diskutil unmountDisk /dev/diskX
sudo dd if=streamscene-client-<version>.img of=/dev/rdiskX bs=1m
diskutil eject /dev/diskX

# Linux
lsblk
sudo dd if=streamscene-client-<version>.img of=/dev/sdX bs=4M status=progress
sync
```

### One card, one identity

Each card gets a **unique device UUID generated on its first boot** by
`streamscene-firstboot.service`. The image itself contains no UUID.

> Do not clone a *booted* card to make more cards. It will have a UUID
> baked in, and every clone will collide as the same device on the server.
> Always flash from the original `.img`.

---

## Part 3 - What the recipient does

No terminal required. This is the part to put on a card in the box.

1. **Plug the frame into power.** Allow 60-90 seconds for the first boot.
2. **Connect a phone to the WiFi network `StreamScene-XXXX`**
   (password `streamscene`). `XXXX` is unique to the device.
3. **The setup page opens automatically.** If it does not, browse to
   `http://192.168.4.1`.
4. **Enter the home WiFi name and password.** The frame joins that network
   and the `StreamScene-` network disappears.
5. **Scan the QR code shown on the display** with the phone camera.
6. **Sign in and give the frame a name.** It is ready.

### Expected timeline

| Time | What happens |
|---|---|
| 0:00 | Power on |
| ~0:30 | First boot provisioning: UUID generated, services enabled |
| ~0:45 | Client starts, finds no WiFi credentials |
| ~1:00 | `StreamScene-XXXX` hotspot appears |
| ~1:15 | Captive portal ready |

### Things to tell them up front

- **2.4 GHz WiFi only.** The Pi Zero 2 W cannot see a 5 GHz-only network.
  If the home router uses one SSID for both bands this is usually fine; if
  the 5 GHz network has its own name, they must pick the 2.4 GHz one.
- **WiFi name and password are case-sensitive.**
- **The display takes ~30 seconds to redraw.** That is normal for E Ink,
  not a fault. Content rotates no faster than every 60 seconds.
- **They need an account before step 6.** Accounts are created manually in
  Authentik - set theirs up before handing over the device.

---

## Part 4 - Supporting a device you cannot reach

Every troubleshooting path currently requires SSH, which recipients will not
use. In practice, ask them to observe and report:

| Symptom | Most likely cause |
|---|---|
| No `StreamScene-XXXX` network after 2 min | Card flashed with stock Pi OS instead of this image |
| Hotspot appears, portal does not open | Browse to `http://192.168.4.1` manually |
| Portal accepts WiFi, device never comes back | Wrong password, or a 5 GHz-only SSID |
| Connects but no QR code appears | Display fault - see [known gaps](#known-gaps) |
| Nothing at all, no LED activity | Power supply or card seating |

With SSH (once it is on their WiFi):

```bash
ssh pi@streamscene.local          # or pi@<ip>, password: streamscene
sudo journalctl -u streamscene-client -f
cat /var/log/streamscene-firstboot.log
~/streamscene-client/view_logs.sh all
```

---

## Known gaps

Track these before wider distribution:

- **The E Ink display path is unproven.** SPI is now enabled and the
  Waveshare driver is vendored, but no device has yet rendered to a panel.
  `waveshare_epd/epdconfig.py` only selects the Raspberry Pi backend when
  `/proc/cpuinfo` reports "Raspberry", so this cannot be tested off-device.
- **Shared default credentials.** Every device ships `pi` / `streamscene`
  with hotspot password `streamscene`. Acceptable for family; not for
  anything wider.
- **No account self-service.** Deliberate - accounts are added by hand in
  Authentik.
- **No QR sticker process.** Referenced in `CLAUDE.md` as a design decision;
  nothing produces them.
- **Build chroot lacks bind mounts** for `/dev`, `/proc`, `/sys`, `/dev/pts`.
  Harmless today; a latent fragility across base-image updates.

---

## Related documentation

- `SD_CARD_IMAGE.md` - image internals and reference
- `TROUBLESHOOTING.md` - log analysis
- `../development/REMOTE_DEBUG.md` - debugging a device at someone else's house
- `WIFI_SETUP.md` - **development only**, not the distribution path
- `../../client/waveshare_epd/VENDOR.md` - vendored display driver provenance

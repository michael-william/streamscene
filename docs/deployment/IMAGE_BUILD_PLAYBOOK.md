# StreamScene Image Build Playbook

**Purpose:** everything learned while getting `build_sd_image.sh` to produce a
device that actually works. Written as a handoff for a future session.

**Last updated:** 2026-09-07 · current version `1.2.1`

> Read this before touching `build_sd_image.sh`, `client/setup/`, or
> `client/main.py`. Most of what is written here was learned by breaking a
> device and reading its SD card afterwards.

---

## 1. The one rule

**Change one thing per image.**

Two separate outages during this work came from bundling an unrequested
"improvement" with a real fix:

| Added | Consequence |
|---|---|
| `CapabilityBoundingSet=CAP_NET_BIND_SERVICE` alongside `AmbientCapabilities` | Dropped `CAP_SETUID`, so every `sudo` call failed, so `ExecStartPre` failed, so the service never started. Device did nothing at all - no hotspot, no display change, no LAN presence. |
| `dhcpcd5` installed to fix a missing binary | Its daemon auto-starts and manages *all* interfaces, so it claimed `wlan0` and destabilised the hotspot. Phones reported **"wrong password"** on a correct passphrase. |

Both looked harmless. Both cost a build/flash/test cycle plus a long
misdiagnosis. When a device that worked stops working, **diff against the last
good image first** rather than theorising.

---

## 2. Where things live

| Thing | Location | Notes |
|---|---|---|
| Source of truth | CT118 `/root/streamscene` | Repo `git@github.com:michael-william/streamscene.git` |
| Build tree | Proxmox host `/root/streamscene-build` | Staged from CT118; only `build_sd_image.sh`, `client/`, `config/`, `scripts/` |
| **Stale checkout - do not use** | Proxmox host `/root/streamscene` | Nov 2025 copy, diverged. Easy to build from by accident. |
| Bench machine | `wibaut-satellite-s50-b` (tailnet, `192.168.1.206`) | Linux, **has an SD card reader**, `rpi-imager` installed, `root` SSH works from the Proxmox host as `badgy` |
| Built images | host `/root/streamscene-build/*.img`, copies in `/home/badgy/streamscene-images/` | `/root` is mode 700, so stage a copy before `scp` as `badgy` |

### Build location constraints

- **Must build on the Proxmox host.** CT118 has the tools but **no `/dev/loop*`**,
  so it cannot loop-mount the image.
- **Cannot build on macOS** - no loop devices, no ext4, no foreign-arch chroot.
- `sudo scp` from the host fails: root has no SSH key for the satellite. Copy as
  `badgy` from `/home/badgy/streamscene-images/`.

### `pct exec` trap

Always pipe its output (`| cat` at minimum). Unpiped, it clobbers the caller's
output capture and the command appears to fail.

---

## 3. Running a build

```bash
# refresh the build tree from CT118
sudo rm -rf /root/streamscene-build/client /root/streamscene-build/scripts
sudo pct exec 118 -- tar -C /root/streamscene -cf - \
    --exclude='__pycache__' --exclude='*.bak*' \
    build_sd_image.sh client config scripts \
  | sudo tar -C /root/streamscene-build -xf -

cd /root/streamscene-build && sudo ./build_sd_image.sh
```

~5-8 minutes. Ends with `image verification passed` then `✓ Build Complete!`.
**Anything else means do not flash the output.**

### Dev images (WiFi pre-seeded)

```bash
DEV_WIFI_SSID=... DEV_WIFI_PSK=... sudo -E ./build_sd_image.sh
```

Output is named `...-DEV-DO-NOT-DISTRIBUTE.img` and contains a plaintext WiFi
password.

> **Pre-seeding conflicts with the hotspot fallback.** `_handle_wifi_setup`
> skips the hotspot entirely when credentials exist, so a device that fails to
> connect retries the same dead network forever instead of opening a hotspot.
> The offline path calls `_quarantine_wifi_credentials()` to work around this,
> but for debugging prefer a normal image and type credentials into the portal.

### Flashing from the satellite

```bash
# identify: sda = 238G system disk (NEVER), sdb = 59.5G removable card
lsblk -o NAME,SIZE,TYPE,FSTYPE,LABEL,MOUNTPOINT
umount /dev/sdb1 /dev/sdb2
dd if=/home/wibaut/streamscene-client-<ver>.img of=/dev/sdb bs=4M conv=fsync status=progress
sync
```

A raw byte-compare after `partprobe` will **not** match: the desktop
automounter remounts both partitions and ext4 journal replay rewrites blocks.
Verify by mounting and checking file contents instead.

---

## 4. Bugs found and fixed

All confirmed from device logs, not inferred.

### 4.1 Every card had the same device UUID *(pre-existing)*

`build_sd_image.sh` generated a UUID at **build** time and wrote it into
`/boot/firmware/streamscene-device.txt`, so every card flashed from one image
claimed the same identity on the server.

**Fix:** removed. `streamscene-firstboot.service` runs `client/first_boot.sh` on
each device's first boot to generate a unique UUID. **Never reinstate a
build-time UUID.** Also: never clone a *booted* card - clone from the `.img`.

### 4.2 `streamscene-firstboot.service` did not exist *(pre-existing)*

`SD_CARD_IMAGE.md` documented it; `first_boot.sh` existed and even deletes the
unit on completion. The unit file itself was never written, so nothing ran.

**Fix:** created `client/streamscene-firstboot.service`, ordered
`Before=streamscene-client.service` with
`ConditionPathExists=/home/pi/streamscene-client/first_boot.sh` for one-shot
behaviour.

### 4.3 SPI disabled - E Ink could never work *(pre-existing)*

`config.txt` shipped with `#dtparam=spi=on` commented out. The Waveshare HAT is
SPI.

**Fix:** the build enables it, handling all three states (already on, commented,
absent) so it can't produce a duplicate line.

### 4.4 `waveshare-epd` is not on PyPI *(pre-existing)*

It was listed in `client/requirements.txt`. pip resolves before installing, so
one bad name **aborted the entire transaction** - the venv ended up with no
`pillow`, `requests` or `qrcode` either, and the build reported success.

**Fix:** driver vendored at `client/waveshare_epd/` (see its `VENDOR.md`;
upstream commit `a794fbc3`). Requirements gained `spidev`, `gpiozero`, `lgpio`.

> `waveshare_epd/epdconfig.py` does platform detection **at import time** by
> grepping `/proc/cpuinfo` for "Raspberry". It can only be imported on real Pi
> hardware - never in the build chroot. `verify_image.py` therefore checks the
> driver **statically** (files present, compile, panel geometry 800x480 via
> `ast`), and does not import it.

### 4.5 Captive portal never reachable on port 80 *(pre-existing)*

The portal bound `8080` and relied on an iptables `REDIRECT`. That rule could
never apply: **`iptables` is not installed** on Pi OS Bookworm (nft only), and
it was absent from `sudoers.streamscene`. The failure was caught and logged as a
*warning*, so the device looked healthy while port 80 - the only port captive
portal detection probes - was dead.

**Fix:** `AmbientCapabilities=CAP_NET_BIND_SERVICE` on the unit; portal binds 80
directly. Both `sudo iptables` calls deleted. `setcap` on the system Python
removed from `first_boot.sh` (it granted every Python process the privilege and
was wiped by `apt upgrade`).

### 4.6 `wpa_supplicant` masked and never unmasked *(pre-existing - the big one)*

```
[HOTSPOT] Step 5: Restarting wpa_supplicant for client mode
[ERROR] Failed to start wpa_supplicant.service: Unit wpa_supplicant.service is masked.
```

`create_hotspot()` masks `wpa_supplicant` so it can't grab `wlan0` in AP mode.
`stop_hotspot()` called `systemctl start` on it - **a masked unit cannot
start**. `hostapd` was unmasked on the way in; `wpa_supplicant` never was on the
way out. **Once the hotspot had run, the device could never join WiFi again.**

**Fix:** unmask before start, and log an error if the start still fails.
`sudoers.streamscene` already permitted the unmask - it was simply never called.

### 4.7 No DHCP client installed *(pre-existing)*

`wifi_client.py` shells out to `dhcpcd` ("Raspberry Pi OS default" - true before
Bookworm). Bookworm ships NetworkManager instead, and `first_boot.sh` **masks
NetworkManager**. So `wpa_supplicant` could associate and **nothing would ever
request a lease** - no IP, connection reported as failed with no useful message.

**Fix:** install `dhcpcd5`, but **disable and mask its daemon** (see 4.8).

### 4.8 `dhcpcd5` daemon broke the hotspot *(introduced by the fix for 4.7)*

Installing the package enables `dhcpcd.service`, which manages **all** interfaces
by default. It claimed `wlan0`, fought the hotspot's static `192.168.4.1`, and
clients failed association - surfacing as **"wrong password"**.

**Fix:** remove the enablement symlinks and mask the unit **by direct file
operations** - `systemctl disable` does not work reliably in a chroot (no D-Bus)
and silently no-ops:

```bash
rm -f /etc/systemd/system/multi-user.target.wants/dhcpcd.service
rm -f /etc/rc[0-9S].d/S[0-9][0-9]dhcpcd
ln -sf /dev/null /etc/systemd/system/dhcpcd.service
```

The **binary** stays; `wifi_client.py` invokes it per-interface on demand.

### 4.9 The chroot had no `/proc`, `/sys`, `/dev` *(pre-existing, latent)*

The build never bind-mounted kernel filesystems. Harmless until `dhcpcd5` pulled
in packages that trigger `initramfs-tools`, whose postinst needs `/sys`:

```
mkinitramfs: MODULES dep requires mounted sysfs on /sys
dpkg: error processing package initramfs-tools
```

`apt` exited non-zero, and because the chroot script runs under `set -e`,
**everything after the package install silently never ran.** Every image built
before this fix had a partially-failed package install.

**Fix:** bind-mount `/proc`, `/sys`, `/dev`, `/dev/pts` before the chroot;
unmount immediately after and in the `cleanup()` trap, deepest-first, so a
failed build cannot leave host mounts pinned inside the image.

### 4.10 `AWAITING_REGISTRATION -> WIFI_SETUP` was not a legal transition *(introduced)*

The offline fallback called `transition_to(WIFI_SETUP)`, which returned `False`.
The return value was ignored, so the state never changed and the main loop
re-entered the same handler **every ~20 seconds**, redrawing the panel each
time and never reaching the hotspot code.

**Fix:** added `WIFI_SETUP` to the allowed transitions from
`AWAITING_REGISTRATION`; the return value is now checked with an `ERROR`
fallback; and a 30s sleep prevents any recovery path from hammering the panel
(E Ink refreshes are ~30s and the panel has a finite refresh life).

### 4.11 Registration dead-ended after 30 minutes *(pre-existing)*

`wait_for_registration(timeout=1800)` transitioned to `ERROR` on expiry, leaving
a QR code on screen with **no poll behind it** - indistinguishable from a
working device. Registering an hour after plugging in is normal behaviour.

**Fix:** 10-minute cycles that re-enter `AWAITING_REGISTRATION` (re-checking
connectivity) instead of failing.

### 4.12 `is_connected()` returned true in AP mode *(pre-existing)*

It accepted **any** `scope global` address on `wlan0` - and the hotspot's own
`192.168.4.1` qualifies. The device would report "connected" while running as an
access point connected to nothing, advance to registration, and show a QR code
while offline.

**Fix:** `HOTSPOT_IP` explicitly rejected; added `is_online()` which opens a real
TCP connection. **Link state is not reachability.**

### 4.13 Silent failure fallbacks *(pre-existing, a category not a bug)*

Three places claimed success or "we'll retry later" on unsurvivable failures:

- venv install failure → "will retry on first boot" *(no network at first boot)*
- apt failure → "packages will install on first boot" *(same)*
- iptables failure → warning, portal left unreachable

**All three now abort the build.** A device cannot repair itself before the
captive portal has run, because the portal is the Python that needs those
packages.

### 4.14 Misleading first-boot warning *(pre-existing, cosmetic)*

`first_boot.sh` ran `systemctl is-active` on a unit ordered *after* itself, so it
always printed `✗ Warning: Service may not have started correctly` on a healthy
boot. Removed - it sent people chasing a non-problem.

---

## 5. Guard rails now in the build

`scripts/verify_image.py` runs **inside the image** via chroot using the image's
own venv, with the client directory as cwd - the same way the service runs
`main.py`. It reports **all** failures rather than stopping at the first, and a
failure **aborts the build**.

| Check | Catches |
|---|---|
| `venv OK` | pillow / requests / qrcode importable |
| `gpio OK` | spidev / gpiozero / lgpio importable |
| `driver OK` | vendored `waveshare_epd` present, compiles, panel is 800x480 |
| `client OK` | `main.py` compiles |
| `network OK` | `dhcpcd`, `wpa_supplicant`, `wpa_cli`, `hostapd`, `dnsmasq`, `rfkill` all exist **and `dhcpcd.service` is not enabled at boot** |
| `wifi` | reports whether credentials are pre-seeded (DEV image marker) |

It caught the broken `systemctl disable` on its first run, before a flash.

**When you fix a bug in the image, add a check here.** That is the highest-value
habit from this work.

---

## 6. Debugging playbook

**Do not iterate by rebuilding and reflashing.** A build/flash/test cycle is
~10 minutes and produces guesses. Reading the card takes ~5 minutes and produces
answers. Three root causes came out of one card read.

### Read the card

1. Pull the SD card, insert into the satellite's reader
2. It automounts (`/media/wibaut/rootfs` or `/media/devmon/rootfs`)
3. From the Proxmox host:

```bash
ssh root@wibaut-satellite-s50-b
R=/media/devmon/rootfs        # confirm with: lsblk -no MOUNTPOINT /dev/sdb2
tail -60 $R/var/log/streamscene/streamscene-wifi.log
tail -40 $R/var/log/streamscene/streamscene-hotspot.log
tail -40 $R/var/log/streamscene/streamscene-registration.log
cat $R/home/pi/streamscene-client/device_state.json
ls -l $R/home/pi/streamscene-client/*.json*      # .failed = quarantine fired
cat $R/var/log/streamscene-firstboot.log
```

These log files persist across reboots. **The systemd journal does not** - see
open items.

### On-device (when the hotspot is up)

```bash
# join StreamScene-XXXX, password: streamscene
ssh pi@192.168.4.1                    # password: streamscene
sudo journalctl -u streamscene-client -n 100 --no-pager
sudo systemctl is-active wpa_supplicant; sudo wpa_cli -i wlan0 status
ip addr show wlan0
```

### From the Proxmox host

```bash
# did a Pi join the LAN?
for i in $(seq 1 254); do (ping -c1 -W1 192.168.1.$i >/dev/null 2>&1 &); done; sleep 6
ip neigh | grep -iE "b8:27:eb|dc:a6:32|e4:5f:01|2c:cf:67|d8:3a:dd"

# device + API key status, WITHOUT consuming the key
sudo pct exec 118 -- su - postgres -c "psql -d streamscene -x -c \"SELECT device_uuid, nickname, CASE WHEN config::jsonb ? 'pending_api_key' THEN 'PENDING' ELSE 'COLLECTED' END, last_seen FROM devices ORDER BY registered_at DESC;\"" 2>&1 | cat
```

> **Never `curl` `/api/devices/<uuid>/registration-status` yourself.** The server
> returns the API key **once** then clears it. Curling it burns the key and the
> device can never collect it.

### Scan for WiFi bands (settles "is there 2.4GHz?")

```bash
ssh root@wibaut-satellite-s50-b 'nmcli -f SSID,FREQ,SIGNAL,SECURITY dev wifi list --rescan yes'
```

`Louisiamsterdam-TP` broadcasts on **both** 2442/2452 MHz and 5200 MHz. The Pi
Zero 2 W is 2.4 GHz only, but this network is band-steered so that is fine.
**The band was never the problem** - do not go down this path again.

---

## 7. Status

### Confirmed working on hardware

- E Ink display renders (SPI enabled, vendored driver loads on real hardware)
- First-boot provisioning, unique UUID per card
- WiFi hotspot `StreamScene-XXXX` / `streamscene`
- Captive portal, auto-opening on port 80
- Server-side registration, device row bound to correct `device_uuid`
- Hotspot fallback when offline (the `states.py` fix)

### Not yet confirmed end to end

- **WiFi client association + DHCP lease.** Fixes 4.6, 4.7 and 4.8 all address
  this and none has been observed working yet. This is the next thing to verify.
- Device collecting its API key and leaving the QR screen
- Content display / rotation (Phase 7 onward)

### Verified non-issues (do not re-investigate)

- WiFi band - 2.4 GHz is present at full signal
- WiFi password - hash-compared against the working PSK, identical
- Hotspot password - still `streamscene`, unchanged in code
- hostapd config - TKIP/`country_code=US` is the config that demonstrably
  accepted clients. Changing it was a guess and was reverted.

---

## 8. Open items

**Security (must fix before distributing):**

- `device_state.json` and `wifi_credentials.json*` store the **WiFi password in
  plaintext**, mode 644. Fine on a bench, not on someone else's device.
- Every device ships `pi` / `streamscene` and hotspot password `streamscene`.
- `hotspot.py` logs the hotspot password at INFO.

**Reliability:**

- **journald is not persisting** despite `/var/log/journal` existing, so
  `hostapd` and `wpa_supplicant`'s own messages are lost on reboot. Set
  `Storage=persistent` in `journald.conf` - would have saved hours.
- No `OnFailure=` unit. When the client service fails to start, the panel keeps
  showing whatever was there before. A device that can't start looks identical
  to a working one.
- Ordering: the dev-WiFi seeding must run **before** `verify_image.py`, or the
  `wifi` check reports the wrong thing. Already fixed; don't reintroduce.

**Repo hygiene:**

- **Significant unpushed work in CT118**, including the whole OTA client
  (`client/services/`), `client/waveshare_epd/`, `scripts/verify_image.py`,
  `client/streamscene-firstboot.service`, and all of the above fixes. The push
  is blocked on a passphrase-protected SSH key - needs `pct enter 118` and
  `ssh-add` interactively.
- Backups of every file modified in this work: `*.bak-preclaude`,
  `*.bak2-preclaude`.
- Docs updated: `DISTRIBUTION.md` (new), `REMOTE_DEBUG.md` (new),
  `SD_CARD_IMAGE.md`, `WIFI_SETUP.md` (marked dev-only), `CLAUDE.md`.

---

## 9. Key files

| File | Role |
|---|---|
| `build_sd_image.sh` | Image builder. Runs on the Proxmox host only. |
| `scripts/verify_image.py` | In-image verification; aborts the build on failure. |
| `client/first_boot.sh` | Per-device provisioning; self-deletes. |
| `client/streamscene-firstboot.service` | Runs the above, ordered before the client. |
| `client/streamscene-client.service` | Main unit. `AmbientCapabilities` only - see 4.5. |
| `client/setup/hotspot.py` | AP mode. Masks/unmasks `wpa_supplicant` - see 4.6. |
| `client/setup/wifi_client.py` | Client mode, `is_connected()`, `is_online()`, DHCP. |
| `client/setup/setup_manager.py` | Captive portal on port 80. |
| `client/states.py` | State machine + `VALID_TRANSITIONS` - see 4.10. |
| `client/main.py` | State handlers, offline fallback, credential quarantine. |
| `client/waveshare_epd/` | Vendored display driver + `VENDOR.md`. |
| `config/sudoers.streamscene` | Whitelist. A command missing here fails silently-ish. |

---

## 10. Advice for the next session

1. **Read the card before changing code.** It is the fastest, most reliable
   source of truth available.
2. **Change one thing per image**, and diff against the last working image when
   something regresses.
3. **Add a `verify_image.py` check for every bug you fix.** It caught a broken
   fix within one build.
4. **Distrust every "will retry later" fallback.** The device cannot self-heal
   before the portal runs.
5. **Do not theorise about the WiFi band or the password.** Both were measured
   and ruled out; see §6.
6. If the user says "it worked before", **believe them and go find the diff** -
   that instinct was right twice and my reasoning was wrong.

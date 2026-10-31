# Remote Device Debugging (Environment B)

Iterating on a StreamScene device that is at **somebody else's house**, with a
helper who has a laptop and the hardware but is not going to debug it for you.

> **Status: partially unverified.** The USB transport described in
> [Option 2](#option-2--usb-gadget-networking) has not yet been confirmed
> working end to end. Update this doc once it has.

For the two other environments see the table in
`../deployment/DISTRIBUTION.md`.

---

## At home: the bench debug image

For the home bench (Pi on a USB-ethernet dongle on the LAN) there is a built
debug image: `sudo ./build_sd_image.sh --debug` (wrapper on the Proxmox host:
`/root/streamscene-build/build_debug.sh`, which publishes the `.img.xz` to the
NAS share `Tailgate/StreamScene-images/` for Raspberry Pi Imager). It keeps you
on the device through every phase, hotspot included:

- **eth0 is owned by systemd-networkd**, not the client. Shipped images mask
  NetworkManager and the dhcpcd daemon and the WiFi code runs
  `pkill -9 dhcpcd`, so on a normal image the dongle gets one lease at most and
  then drops off the network. That is why the bench Pi kept vanishing.
- **root SSH by key**, plus **Tailscale** (`ssh root@streamscene-debug`).
- **Logs**: persistent journal (`journalctl -b -1`) and live upload to CT118
  (`journalctl -D /var/log/journal/remote ...`), with a 30s
  `streamscene-heartbeat` line giving IPs, mode and client state.
- **`reset-to-firstboot [--full]`** re-runs onboarding without reflashing.

No WiFi is pre-seeded, so the real hotspot + captive portal flow runs while you
watch over eth0. Details and file list: `debug/README.md`. A normal build
aborts if any debug artifact is present.

---

## The problem

The distribution flow (hotspot → captive portal → QR) is designed so a
recipient never needs a terminal. That is exactly what makes it hard to debug:
when it fails, there is no shell, and the device is not on your network.

You need a shell on the device, without asking the helper to do anything
beyond plugging things in.

---

## Option 1 - Tailscale on the device (recommended)

Since you build the image, put Tailscale *in* it. The device joins your tailnet
the moment it has any working network, and you SSH it directly from CT118 - no
hop through the helper's machine.

**Chicken-and-egg:** Tailscale needs a network, and the device has none until
WiFi setup completes. Break the loop by pre-configuring WiFi in the image, per
`SD_CARD_IMAGE.md` → *Pre-Configure WiFi*: write the helper's SSID and password
to `/home/pi/streamscene-client/wifi_credentials.json` with `"configured": true`
before flashing. The device skips the hotspot entirely and comes straight up on
your tailnet.

This is right for **debugging** - you are working on Phase 6 display code, not
on the captive portal. Validate the real onboarding flow separately, on a card
without pre-configured credentials.

**Never ship this to a recipient.** A debug card carries your auth key and
someone else's WiFi password. Build distribution cards from an unmodified image.

Sketch of what to add to the build (not yet implemented):

- install Tailscale in the chroot
- a first-boot unit running `tailscale up` with an **ephemeral, pre-authorized,
  tagged** auth key, so stale nodes clean themselves up

---

## Option 2 - USB gadget networking

Pi Zero 2 W can present itself as a USB network adapter to the host it is
plugged into. The helper plugs the Pi into their Mac and you reach it through
their machine.

This requires **edits to the boot partition after flashing**, which means a
debug card is not the same artifact as a shipping card.

On the card's boot partition (`/boot/firmware` once booted, the FAT partition
when mounted on another machine):

- `config.txt`: add `dtoverlay=dwc2`
- `cmdline.txt`: insert `modules-load=dwc2,g_ether` immediately after
  `rootwait` - it must stay a **single line**, space-separated

Then the Pi appears as an ethernet interface on the Mac (typically
`192.168.x.x` link-local, or via `raspberrypi.local`/`streamscene.local`).

**Critical:** the Pi must be plugged into the port marked **USB**, not the one
marked **PWR IN**. Only the data port speaks USB gadget. This is the single
most common reason "nothing happens".

Confirm the two `config.txt`/`cmdline.txt` edits are actually present before
blaming the hardware - the stock image has neither.

---

## Option 3 - Reach the helper's Mac

Whichever transport gets you to the device, you may also want the Mac itself.

**Tailscale (preferred):** they install it and sign in to your tailnet
(invite, or a single-use auth key). Then:

```bash
ssh helper@their-mac        # needs Remote Login enabled in System Settings
```

or `tailscale up --ssh` on the Mac, which avoids key exchange and macOS
Remote Login entirely.

**Screen sharing:** for the physical half - reseating the HAT, reading HDMI
boot output, checking LEDs - a shell tells you nothing. Zoom/FaceTime
screenshare, or macOS Screen Sharing over Tailscale (`vnc://their-mac`).

Do not bother with reverse SSH tunnels or ngrok if Tailscale is available;
they add moving parts and break on reconnect.

---

## Recommended setup

1. Build a **debug card**: image + pre-configured WiFi + Tailscale.
2. Helper flashes it once and powers the Pi on.
3. Device joins your tailnet; you SSH from CT118 and iterate freely.
4. Keep screen sharing available for anything physical.

This removes the helper from the loop after the flash, which is the real win -
you get a shell on the device instead of pair-debugging over text.

---

## What you cannot debug remotely

- **Whether the panel physically renders.** You can confirm the driver loads
  and the code runs; only a person in the room can confirm the picture.
- **Card seating, HAT alignment, power supply adequacy.** Ask for a photo.
- **Which USB port they used.** Ask explicitly; do not assume.

---

## Before blaming the software

Most "it never worked" reports have turned out to be one of:

| Cause | Check |
|---|---|
| Flashed stock Raspberry Pi OS, not the StreamScene image | Is there a `StreamScene-XXXX` hotspot at all? |
| Pi plugged into the PWR port instead of the USB port | Ask which port |
| 5 GHz-only SSID | Pi Zero 2 W is 2.4 GHz only |
| Imager's OS customisation left on | It overwrites the image's own config |
| Half-built or hand-edited image | `sha256sum -c` the image before flashing |

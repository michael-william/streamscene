# Debug image overlay

Installed ONLY by `sudo ./build_sd_image.sh --debug`. Never ship a card built
this way: it carries a root SSH key, a Tailscale auth key, and forwards the
whole journal to the dev server. The build refuses to finish a normal image if
any of these leak in.

What each file gives you:

| File | Purpose |
|---|---|
| `eth0.network` | systemd-networkd owns the USB-ethernet dongle (`eth0`/`enx*`). The client's `pkill -9 dhcpcd` and the hotspot code cannot touch it, so the bench link survives hotspot mode, WiFi joins and client restarts. |
| `client-ignore-eth0.conf` | Sets `STREAMSCENE_ETHERNET_ENABLED=false` for the client, so it ignores eth0 and runs the real hotspot/captive-portal flow. |
| `networkd-foreign.conf` | Stops networkd deleting the routes dhcpcd/hostapd put on `wlan0`. |
| `journald-persistent.conf` | Journal survives reboots: `journalctl -b -1` shows the boot that died. |
| `journal-upload.conf` + `journal-upload-restart.conf` | Streams the journal live to CT118 (`systemd-journal-remote` on :19532), retrying forever. |
| `streamscene-tailscale-up.service` | Joins the tailnet with the ephemeral, tagged debug key. |
| `streamscene-heartbeat.*` | Every 30s logs IPs, network mode, client state, Tailscale IP to the journal (and therefore to CT118). |
| `reset-to-firstboot` | Re-run onboarding without reflashing. |

Reading logs on CT118:

    journalctl -D /var/log/journal/remote -t streamscene-heartbeat -n 5
    journalctl -D /var/log/journal/remote -u streamscene-client -f

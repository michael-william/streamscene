#!/bin/bash
# Debug image only. One line per run so it greps well on CT118.
addr() { ip -4 -o addr show dev "$1" 2>/dev/null | awk '{print $4}' | paste -sd, -; }
if systemctl is-active --quiet hostapd; then mode=hotspot
elif wpa_cli -i wlan0 status 2>/dev/null | grep -q '^wpa_state=COMPLETED'; then mode=wifi-client
else mode=no-wifi; fi
echo "eth0=$(addr eth0) wlan0=$(addr wlan0) mode=$mode" \
     "client=$(systemctl is-active streamscene-client)" \
     "ts=$(tailscale ip -4 2>/dev/null | head -1)" \
     "uptime=$(cut -d' ' -f1 /proc/uptime)s"

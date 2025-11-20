#!/bin/bash
# StreamScene WiFi Hotspot Diagnostic Script
# Generated: 2025-11-18
# Purpose: Comprehensive diagnostics for troubleshooting WiFi hotspot issues

echo "=========================================="
echo "StreamScene Diagnostic Report"
echo "Generated: $(date)"
echo "Hostname: $(hostname)"
echo "=========================================="
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "CRITICAL CHECKS"
echo "=========================================="
echo ""

# Check 1: First Boot Completion
echo "--- CHECK 1: First Boot Completion ---"
if [ -f /var/lib/streamscene-firstboot-complete ]; then
    echo -e "${GREEN}✓${NC} First boot completed"
    echo "  Timestamp: $(stat -c %y /var/lib/streamscene-firstboot-complete)"
else
    echo -e "${RED}✗${NC} First boot NOT completed (CRITICAL)"
    echo "  This means the provisioning script never ran successfully"
fi
echo ""

# Check 2: Device UUID
echo "--- CHECK 2: Device UUID File ---"
if [ -f /boot/firmware/streamscene-device.txt ]; then
    uuid=$(cat /boot/firmware/streamscene-device.txt)
    echo -e "${GREEN}✓${NC} UUID file exists"
    echo "  UUID: $uuid"
else
    echo -e "${RED}✗${NC} UUID file missing (CRITICAL)"
    echo "  Expected: /boot/firmware/streamscene-device.txt"
fi
echo ""

# Check 3: Python venv
echo "--- CHECK 3: Python Virtual Environment ---"
if [ -f /home/pi/streamscene-client/venv/bin/python3 ]; then
    echo -e "${GREEN}✓${NC} venv exists"
    venv_python=$(/home/pi/streamscene-client/venv/bin/python3 --version 2>&1)
    echo "  Version: $venv_python"

    # Check if packages installed
    pkg_count=$(/home/pi/streamscene-client/venv/bin/pip list 2>/dev/null | wc -l)
    echo "  Packages installed: $pkg_count"

    if [ $pkg_count -lt 10 ]; then
        echo -e "  ${YELLOW}⚠${NC} WARNING: Very few packages installed (expected 20+)"
    fi
else
    echo -e "${RED}✗${NC} venv missing (CRITICAL)"
    echo "  Expected: /home/pi/streamscene-client/venv/bin/python3"
fi
echo ""

# Check 4: WiFi Hardware (rfkill)
echo "--- CHECK 4: WiFi Hardware Status ---"
if command -v rfkill &> /dev/null; then
    rfkill_output=$(rfkill list wifi)
    echo "$rfkill_output"

    if echo "$rfkill_output" | grep -q "Soft blocked: yes"; then
        echo -e "${RED}✗${NC} WiFi is SOFT BLOCKED (CRITICAL)"
    elif echo "$rfkill_output" | grep -q "Hard blocked: yes"; then
        echo -e "${RED}✗${NC} WiFi is HARD BLOCKED (CRITICAL - hardware switch?)"
    else
        echo -e "${GREEN}✓${NC} WiFi is unblocked"
    fi
else
    echo -e "${YELLOW}⚠${NC} rfkill command not found"
fi
echo ""

# Check 5: NetworkManager Status
echo "--- CHECK 5: NetworkManager Status ---"
nm_status=$(systemctl is-active NetworkManager 2>&1)
if [ "$nm_status" = "inactive" ] || [ "$nm_status" = "unknown" ]; then
    echo -e "${GREEN}✓${NC} NetworkManager is stopped ($nm_status)"
else
    echo -e "${RED}✗${NC} NetworkManager is RUNNING (CRITICAL)"
    echo "  Status: $nm_status"
    echo "  This will conflict with manual WiFi control"
fi

nm_enabled=$(systemctl is-enabled NetworkManager 2>&1)
if echo "$nm_enabled" | grep -q "masked"; then
    echo -e "${GREEN}✓${NC} NetworkManager is masked"
elif [ "$nm_enabled" = "disabled" ]; then
    echo -e "${YELLOW}⚠${NC} NetworkManager is disabled but not masked"
else
    echo -e "${RED}✗${NC} NetworkManager is enabled ($nm_enabled)"
fi
echo ""

# Check 6: Python Capabilities (port 80)
echo "--- CHECK 6: Python Port 80 Capabilities ---"
cap_found=0
for python_bin in /usr/bin/python3.11 /usr/bin/python3; do
    if [ -f "$python_bin" ]; then
        caps=$(getcap "$python_bin" 2>&1)
        if echo "$caps" | grep -q "cap_net_bind_service"; then
            echo -e "${GREEN}✓${NC} $python_bin has cap_net_bind_service"
            echo "  $caps"
            cap_found=1
        else
            echo -e "${YELLOW}⚠${NC} $python_bin: $caps"
        fi
    fi
done

if [ $cap_found -eq 0 ]; then
    echo -e "${RED}✗${NC} No Python binary has port 80 capabilities (CRITICAL)"
fi
echo ""

echo "=========================================="
echo "SERVICE STATUS"
echo "=========================================="
echo ""

# Check 7: streamscene-client service
echo "--- CHECK 7: streamscene-client Service ---"
sc_status=$(systemctl is-active streamscene-client 2>&1)
echo "Status: $sc_status"

if [ "$sc_status" = "active" ]; then
    echo -e "${GREEN}✓${NC} Service is running"

    # Check if Python process is actually running
    if ps aux | grep -v grep | grep -q "streamscene-client.*python"; then
        echo -e "${GREEN}✓${NC} Python process found"
    else
        echo -e "${YELLOW}⚠${NC} Service active but no Python process found"
    fi
else
    echo -e "${RED}✗${NC} Service is not running"
fi

echo ""
echo "Service details:"
systemctl status streamscene-client --no-pager -l | head -20
echo ""

# Check 8: hostapd service
echo "--- CHECK 8: hostapd Service ---"
hostapd_status=$(systemctl is-active hostapd 2>&1)
echo "Status: $hostapd_status"

if [ "$hostapd_status" = "active" ]; then
    echo -e "${GREEN}✓${NC} hostapd is running"
else
    echo -e "${YELLOW}⚠${NC} hostapd is not running (expected if not in hotspot mode)"
fi
echo ""

# Check 9: dnsmasq service
echo "--- CHECK 9: dnsmasq Service ---"
dnsmasq_status=$(systemctl is-active dnsmasq 2>&1)
echo "Status: $dnsmasq_status"

if [ "$dnsmasq_status" = "active" ]; then
    echo -e "${GREEN}✓${NC} dnsmasq is running"
else
    echo -e "${YELLOW}⚠${NC} dnsmasq is not running (expected if not in hotspot mode)"
fi
echo ""

# Check 10: wpa_supplicant service
echo "--- CHECK 10: wpa_supplicant Service ---"
wpa_status=$(systemctl is-active wpa_supplicant 2>&1)
echo "Status: $wpa_status"

if [ "$wpa_status" = "active" ]; then
    echo -e "${YELLOW}⚠${NC} wpa_supplicant is running (should be masked in hotspot mode)"
else
    echo -e "${GREEN}✓${NC} wpa_supplicant is not running"
fi

# Check for rogue wpa_supplicant processes
wpa_procs=$(ps aux | grep wpa_supplicant | grep -v grep | wc -l)
if [ $wpa_procs -gt 0 ]; then
    echo -e "${RED}✗${NC} Found $wpa_procs wpa_supplicant processes running"
    ps aux | grep wpa_supplicant | grep -v grep
else
    echo -e "${GREEN}✓${NC} No wpa_supplicant processes"
fi
echo ""

echo "=========================================="
echo "NETWORK CONFIGURATION"
echo "=========================================="
echo ""

# Check 11: wlan0 interface
echo "--- CHECK 11: wlan0 Interface ---"
if ip link show wlan0 &> /dev/null; then
    echo -e "${GREEN}✓${NC} wlan0 interface exists"

    # Check IP address
    wlan0_ip=$(ip addr show wlan0 | grep "inet " | awk '{print $2}')
    if [ -n "$wlan0_ip" ]; then
        echo "  IP Address: $wlan0_ip"

        if echo "$wlan0_ip" | grep -q "192.168.4.1"; then
            echo -e "  ${GREEN}✓${NC} Has hotspot IP (192.168.4.1)"
        else
            echo -e "  ${YELLOW}⚠${NC} Has different IP (not in hotspot mode?)"
        fi
    else
        echo -e "  ${YELLOW}⚠${NC} No IP address assigned"
    fi

    # Check interface state
    wlan0_state=$(ip link show wlan0 | grep -o "state [A-Z]*" | awk '{print $2}')
    echo "  State: $wlan0_state"

    # Check mode
    if command -v iwconfig &> /dev/null; then
        wlan0_mode=$(iwconfig wlan0 2>&1 | grep Mode | awk -F: '{print $2}' | awk '{print $1}')
        echo "  Mode: $wlan0_mode"

        if echo "$wlan0_mode" | grep -q "Master"; then
            echo -e "  ${GREEN}✓${NC} In AP/Master mode (hotspot)"
        elif echo "$wlan0_mode" | grep -q "Managed"; then
            echo -e "  ${YELLOW}⚠${NC} In client/managed mode (not hotspot)"
        fi
    fi
else
    echo -e "${RED}✗${NC} wlan0 interface not found"
fi
echo ""

# Check 12: Port 80 binding
echo "--- CHECK 12: Port 80 Binding ---"
port80=$(sudo netstat -tulpn 2>/dev/null | grep :80 || sudo ss -tulpn 2>/dev/null | grep :80)
if [ -n "$port80" ]; then
    echo -e "${GREEN}✓${NC} Port 80 is bound"
    echo "$port80"
else
    echo -e "${YELLOW}⚠${NC} Port 80 is not bound (captive portal not running)"
fi
echo ""

echo "=========================================="
echo "CONFIGURATION FILES"
echo "=========================================="
echo ""

# Check 13: hostapd.conf
echo "--- CHECK 13: hostapd Configuration ---"
if [ -f /etc/hostapd/hostapd.conf ]; then
    echo -e "${GREEN}✓${NC} /etc/hostapd/hostapd.conf exists"

    ssid=$(grep "^ssid=" /etc/hostapd/hostapd.conf 2>/dev/null | cut -d= -f2)
    country=$(grep "^country_code=" /etc/hostapd/hostapd.conf 2>/dev/null | cut -d= -f2)
    channel=$(grep "^channel=" /etc/hostapd/hostapd.conf 2>/dev/null | cut -d= -f2)

    echo "  SSID: $ssid"
    echo "  Country Code: $country"
    echo "  Channel: $channel"

    if [ -z "$country" ]; then
        echo -e "  ${RED}✗${NC} Country code missing (CRITICAL)"
    else
        echo -e "  ${GREEN}✓${NC} Country code set"
    fi
else
    echo -e "${YELLOW}⚠${NC} /etc/hostapd/hostapd.conf not found (will be created when hotspot starts)"
fi
echo ""

# Check 14: dnsmasq.conf
echo "--- CHECK 14: dnsmasq Configuration ---"
if [ -f /etc/dnsmasq.d/streamscene.conf ]; then
    echo -e "${GREEN}✓${NC} /etc/dnsmasq.d/streamscene.conf exists"

    interface=$(grep "^interface=" /etc/dnsmasq.d/streamscene.conf 2>/dev/null | cut -d= -f2)
    dhcp_range=$(grep "^dhcp-range=" /etc/dnsmasq.d/streamscene.conf 2>/dev/null)

    echo "  Interface: $interface"
    echo "  DHCP Range: $dhcp_range"
else
    echo -e "${YELLOW}⚠${NC} /etc/dnsmasq.d/streamscene.conf not found (will be created when hotspot starts)"
fi
echo ""

# Check 15: WiFi credentials
echo "--- CHECK 15: WiFi Credentials File ---"
if [ -f /home/pi/streamscene-client/wifi_credentials.json ]; then
    echo -e "${GREEN}✓${NC} WiFi credentials file exists"

    # Don't show actual credentials, just structure
    if cat /home/pi/streamscene-client/wifi_credentials.json | jq . &> /dev/null; then
        echo "  Valid JSON format"
        ssid=$(cat /home/pi/streamscene-client/wifi_credentials.json | jq -r .ssid 2>/dev/null)
        echo "  SSID: $ssid"
    else
        echo -e "  ${YELLOW}⚠${NC} Not valid JSON"
    fi
else
    echo -e "${YELLOW}⚠${NC} No saved WiFi credentials (expected on first setup)"
fi
echo ""

# Check 16: Device state
echo "--- CHECK 16: Device State ---"
if [ -f /home/pi/streamscene-client/device_state.json ]; then
    echo -e "${GREEN}✓${NC} Device state file exists"

    if cat /home/pi/streamscene-client/device_state.json | jq . &> /dev/null; then
        state=$(cat /home/pi/streamscene-client/device_state.json | jq -r .state 2>/dev/null)
        echo "  Current State: $state"
    else
        echo -e "  ${YELLOW}⚠${NC} Not valid JSON"
    fi
else
    echo -e "${YELLOW}⚠${NC} No device state file (will be created on first run)"
fi
echo ""

echo "=========================================="
echo "PROCESS INFORMATION"
echo "=========================================="
echo ""

echo "--- Running Processes ---"
echo "Python processes:"
ps aux | grep python | grep -v grep

echo ""
echo "hostapd processes:"
ps aux | grep hostapd | grep -v grep || echo "  None"

echo ""
echo "dnsmasq processes:"
ps aux | grep dnsmasq | grep -v grep || echo "  None"

echo ""
echo "wpa_supplicant processes:"
ps aux | grep wpa_supplicant | grep -v grep || echo "  None (GOOD if in hotspot mode)"

echo ""

echo "=========================================="
echo "LOG ANALYSIS"
echo "=========================================="
echo ""

# Check 17: First boot log
echo "--- CHECK 17: First Boot Log ---"
if [ -f /var/log/streamscene-firstboot.log ]; then
    echo -e "${GREEN}✓${NC} First boot log exists"
    echo ""
    echo "Last 30 lines:"
    tail -30 /var/log/streamscene-firstboot.log
else
    echo -e "${YELLOW}⚠${NC} No first boot log found"
fi
echo ""

# Check 18: Client logs
echo "--- CHECK 18: StreamScene Client Logs (Last 50 lines) ---"
echo "journalctl -u streamscene-client -n 50:"
sudo journalctl -u streamscene-client -n 50 --no-pager
echo ""

# Check 19: Application logs
echo "--- CHECK 19: Application Log Files ---"
if [ -d /var/log/streamscene ]; then
    echo -e "${GREEN}✓${NC} Log directory exists"
    echo "Log files:"
    ls -lh /var/log/streamscene/

    echo ""
    echo "Recent errors in logs:"
    for log in /var/log/streamscene/*.log; do
        if [ -f "$log" ]; then
            errors=$(grep -i "error\|exception\|failed\|critical" "$log" 2>/dev/null | tail -5)
            if [ -n "$errors" ]; then
                echo "--- $(basename $log) ---"
                echo "$errors"
                echo ""
            fi
        fi
    done
else
    echo -e "${YELLOW}⚠${NC} Log directory /var/log/streamscene does not exist"
fi
echo ""

# Check 20: hostapd logs
echo "--- CHECK 20: hostapd Logs (Last 20 lines) ---"
sudo journalctl -u hostapd -n 20 --no-pager
echo ""

# Check 21: dnsmasq logs
echo "--- CHECK 21: dnsmasq Logs (Last 20 lines) ---"
sudo journalctl -u dnsmasq -n 20 --no-pager
echo ""

echo "=========================================="
echo "SUMMARY"
echo "=========================================="
echo ""

# Count critical failures
critical_fail=0

[ ! -f /var/lib/streamscene-firstboot-complete ] && ((critical_fail++)) && echo -e "${RED}✗${NC} First boot not completed"
[ ! -f /boot/firmware/streamscene-device.txt ] && ((critical_fail++)) && echo -e "${RED}✗${NC} Device UUID missing"
[ ! -f /home/pi/streamscene-client/venv/bin/python3 ] && ((critical_fail++)) && echo -e "${RED}✗${NC} Python venv missing"

if rfkill list wifi 2>/dev/null | grep -q "blocked: yes"; then
    ((critical_fail++))
    echo -e "${RED}✗${NC} WiFi blocked by rfkill"
fi

if systemctl is-active NetworkManager 2>/dev/null | grep -q "active"; then
    ((critical_fail++))
    echo -e "${RED}✗${NC} NetworkManager is running"
fi

cap_check=0
for python_bin in /usr/bin/python3.11 /usr/bin/python3; do
    [ -f "$python_bin" ] && getcap "$python_bin" 2>&1 | grep -q "cap_net_bind_service" && cap_check=1
done
if [ $cap_check -eq 0 ]; then
    ((critical_fail++))
    echo -e "${RED}✗${NC} Python lacks port 80 capabilities"
fi

echo ""
if [ $critical_fail -eq 0 ]; then
    echo -e "${GREEN}✓✓✓ No critical failures detected${NC}"
    echo "If hotspot still not appearing, check logs above for runtime errors"
else
    echo -e "${RED}Found $critical_fail critical failure(s)${NC}"
    echo "These must be fixed before hotspot will work"
fi

echo ""
echo "=========================================="
echo "Diagnostic report complete: $(date)"
echo "=========================================="

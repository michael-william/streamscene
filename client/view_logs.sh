#!/bin/bash
# StreamScene Client Log Viewer
# Helper script to view and tail log files

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Determine log directory
if [ -d "/var/log/streamscene" ]; then
    LOG_DIR="/var/log/streamscene"
else
    LOG_DIR="$HOME/streamscene-client/logs"
fi

CLIENT_LOG="$LOG_DIR/streamscene-client.log"
HOTSPOT_LOG="$LOG_DIR/streamscene-hotspot.log"
WIFI_LOG="$LOG_DIR/streamscene-wifi.log"
REGISTRATION_LOG="$LOG_DIR/streamscene-registration.log"

# Function to display usage
usage() {
    echo -e "${GREEN}StreamScene Client Log Viewer${NC}"
    echo ""
    echo "Usage: $0 [OPTION]"
    echo ""
    echo "Options:"
    echo "  all          - View all logs (tail -f all files)"
    echo "  client       - View client log only"
    echo "  hotspot      - View hotspot setup log only"
    echo "  wifi         - View WiFi connection log only"
    echo "  registration - View device registration log only"
    echo "  systemd      - View systemd service journal"
    echo "  errors       - Show only ERROR and CRITICAL lines from all logs"
    echo "  recent       - Show last 100 lines from all logs"
    echo "  list         - List all log files and their sizes"
    echo "  clear        - Clear all log files (requires confirmation)"
    echo ""
    echo "Examples:"
    echo "  $0 all         # Follow all logs in real-time"
    echo "  $0 errors      # Show only errors"
    echo "  $0 recent      # Show recent activity"
}

# Function to check if log file exists
check_log() {
    if [ ! -f "$1" ]; then
        echo -e "${YELLOW}Log file not found: $1${NC}"
        return 1
    fi
    return 0
}

# Main command handler
case "${1:-all}" in
    all)
        echo -e "${GREEN}Following all StreamScene logs (Ctrl+C to stop)...${NC}"
        echo -e "${BLUE}Log directory: $LOG_DIR${NC}"
        echo ""

        # Tail all existing log files
        FILES_TO_TAIL=""
        for log in "$CLIENT_LOG" "$HOTSPOT_LOG" "$WIFI_LOG" "$REGISTRATION_LOG"; do
            if [ -f "$log" ]; then
                FILES_TO_TAIL="$FILES_TO_TAIL $log"
            fi
        done

        if [ -n "$FILES_TO_TAIL" ]; then
            tail -f $FILES_TO_TAIL
        else
            echo -e "${RED}No log files found in $LOG_DIR${NC}"
            exit 1
        fi
        ;;

    client)
        echo -e "${GREEN}Following client log (Ctrl+C to stop)...${NC}"
        if check_log "$CLIENT_LOG"; then
            tail -f "$CLIENT_LOG"
        fi
        ;;

    hotspot)
        echo -e "${GREEN}Following hotspot log (Ctrl+C to stop)...${NC}"
        if check_log "$HOTSPOT_LOG"; then
            tail -f "$HOTSPOT_LOG"
        fi
        ;;

    wifi)
        echo -e "${GREEN}Following WiFi log (Ctrl+C to stop)...${NC}"
        if check_log "$WIFI_LOG"; then
            tail -f "$WIFI_LOG"
        fi
        ;;

    registration)
        echo -e "${GREEN}Following registration log (Ctrl+C to stop)...${NC}"
        if check_log "$REGISTRATION_LOG"; then
            tail -f "$REGISTRATION_LOG"
        fi
        ;;

    systemd)
        echo -e "${GREEN}Following systemd service journal (Ctrl+C to stop)...${NC}"
        journalctl -u streamscene-client -f
        ;;

    errors)
        echo -e "${RED}Showing all ERROR and CRITICAL lines:${NC}"
        echo ""
        for log in "$CLIENT_LOG" "$HOTSPOT_LOG" "$WIFI_LOG" "$REGISTRATION_LOG"; do
            if [ -f "$log" ]; then
                echo -e "${BLUE}=== $(basename $log) ===${NC}"
                grep -E "\[(ERROR|CRITICAL)\]" "$log" | tail -n 50 || echo "No errors found"
                echo ""
            fi
        done
        ;;

    recent)
        echo -e "${GREEN}Last 100 lines from all logs:${NC}"
        echo ""
        for log in "$CLIENT_LOG" "$HOTSPOT_LOG" "$WIFI_LOG" "$REGISTRATION_LOG"; do
            if [ -f "$log" ]; then
                echo -e "${BLUE}=== $(basename $log) ===${NC}"
                tail -n 100 "$log"
                echo ""
            fi
        done
        ;;

    list)
        echo -e "${GREEN}StreamScene Log Files:${NC}"
        echo ""
        if [ -d "$LOG_DIR" ]; then
            ls -lh "$LOG_DIR"
        else
            echo -e "${YELLOW}Log directory not found: $LOG_DIR${NC}"
        fi
        ;;

    clear)
        echo -e "${RED}WARNING: This will delete all log files!${NC}"
        read -p "Are you sure? (yes/no): " confirm
        if [ "$confirm" = "yes" ]; then
            for log in "$CLIENT_LOG" "$HOTSPOT_LOG" "$WIFI_LOG" "$REGISTRATION_LOG"; do
                if [ -f "$log" ]; then
                    rm -f "$log"
                    echo "Deleted: $log"
                fi
            done
            echo -e "${GREEN}All logs cleared${NC}"
        else
            echo "Cancelled"
        fi
        ;;

    -h|--help|help)
        usage
        ;;

    *)
        echo -e "${RED}Unknown option: $1${NC}"
        echo ""
        usage
        exit 1
        ;;
esac

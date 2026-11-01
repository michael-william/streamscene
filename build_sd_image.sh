#!/bin/bash
# StreamScene SD Card Image Builder
#
# This script creates a production-ready Raspberry Pi SD card image with:
# - StreamScene client pre-installed
# - All dependencies configured
# - First-boot provisioning
# - Passwordless sudo for network commands
# - SSH enabled with default credentials
# - Comprehensive logging
#
# Requirements:
# - Debian/Ubuntu Linux (for loop mount support)
# - Root access (sudo)
# - At least 8GB free disk space
# - Internet connection (to download base image)
#
# Usage:
#   sudo ./build_sd_image.sh
#
# Output:
#   streamscene-client-<version>.img (ready to flash to SD card)

set -e  # Exit on error
set -u  # Exit on undefined variable

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLIENT_DIR="$SCRIPT_DIR/client"
CONFIG_DIR="$SCRIPT_DIR/config"
VERSION="1.3.0"
DEBUG_DIR="$SCRIPT_DIR/debug"

# --debug: bench-debug image (see debug/README.md). Adds a root SSH key, a
# Tailscale auth key and live journal forwarding. NEVER distribute.
#   DEBUG_SSH_PUBKEY   file with the public key(s) allowed to SSH in as root
#   DEBUG_TS_AUTHKEY   file holding an ephemeral, tagged Tailscale auth key
DEBUG_IMAGE=0
if [ "${1:-}" = "--debug" ]; then
    DEBUG_IMAGE=1
elif [ -n "${1:-}" ]; then
    echo "Usage: sudo $0 [--debug]" >&2
    exit 2
fi
BUILD_REV="${BUILD_REV:-$(git -C "$SCRIPT_DIR" rev-parse --short HEAD 2>/dev/null || echo nogit)}"

# A dev image (WiFi pre-seeded) is named differently so it cannot be confused
# with a distributable one - it contains a plaintext WiFi password.
if [ "$DEBUG_IMAGE" -eq 1 ]; then
    OUTPUT_IMAGE="streamscene-client-${VERSION}-DEBUG-${BUILD_REV}-$(date +%Y%m%d-%H%M)-DO-NOT-DISTRIBUTE.img"
elif [ -n "${DEV_WIFI_SSID:-}" ]; then
    OUTPUT_IMAGE="streamscene-client-${VERSION}-DEV-DO-NOT-DISTRIBUTE.img"
else
    OUTPUT_IMAGE="streamscene-client-${VERSION}.img"
fi
WORK_DIR="/tmp/streamscene-build-$$"

# Raspberry Pi OS configuration
BASE_IMAGE_URL="https://downloads.raspberrypi.org/raspios_lite_armhf/images/raspios_lite_armhf-2024-11-19/2024-11-19-raspios-bookworm-armhf-lite.img.xz"
BASE_IMAGE_NAME="$(basename "$BASE_IMAGE_URL")"

# SSH credentials (user can change after first boot)
DEFAULT_USER="pi"
DEFAULT_PASSWORD="streamscene"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0;33m' # No Color

# Error handling
trap cleanup EXIT

cleanup() {
    if [ $? -ne 0 ]; then
        echo -e "${RED}Build failed! Cleaning up...${NC}"
    fi

    # Unmount if mounted. Kernel filesystems first, deepest first - the image
    # mounts cannot be released while these are still bound inside them.
    if [ -d "$WORK_DIR/mount" ]; then
        sudo umount "$WORK_DIR/mount/dev/pts" 2>/dev/null || true
        sudo umount "$WORK_DIR/mount/dev" 2>/dev/null || true
        sudo umount "$WORK_DIR/mount/sys" 2>/dev/null || true
        sudo umount "$WORK_DIR/mount/proc" 2>/dev/null || true
    fi
    if mountpoint -q "$WORK_DIR/mount" 2>/dev/null; then
        echo "Unmounting image..."
        sudo umount "$WORK_DIR/mount/boot/firmware" 2>/dev/null || true
        sudo umount "$WORK_DIR/mount" 2>/dev/null || true
    fi

    # Detach loop device
    if [ -n "${LOOP_DEVICE:-}" ]; then
        sudo losetup -d "$LOOP_DEVICE" 2>/dev/null || true
    fi

    # Remove work directory
    if [ -d "$WORK_DIR" ]; then
        sudo rm -rf "$WORK_DIR"
    fi
}

log_step() {
    echo -e "${GREEN}[$(date '+%H:%M:%S')]${NC} $1"
}

log_info() {
    echo -e "${BLUE}  →${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}  ⚠${NC} $1"
}

log_error() {
    echo -e "${RED}  ✗${NC} $1"
}

check_requirements() {
    log_step "Checking requirements..."

    # Check if running as root
    if [ "$EUID" -ne 0 ]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi

    # Check required commands
    for cmd in wget xz losetup parted mkfs.ext4 rsync; do
        if ! command -v $cmd &> /dev/null; then
            log_error "Required command '$cmd' not found"
            exit 1
        fi
    done

    # Check disk space (need at least 8GB)
    AVAILABLE_SPACE=$(df /tmp | tail -1 | awk '{print $4}')
    if [ "$AVAILABLE_SPACE" -lt 8388608 ]; then
        log_error "Insufficient disk space in /tmp (need at least 8GB)"
        exit 1
    fi

    if [ "$DEBUG_IMAGE" -eq 1 ]; then
        for var in DEBUG_SSH_PUBKEY DEBUG_TS_AUTHKEY; do
            if [ ! -s "${!var:-}" ]; then
                log_error "--debug needs $var pointing at a non-empty file"
                exit 1
            fi
        done
        if [ ! -d "$DEBUG_DIR" ]; then
            log_error "--debug needs $DEBUG_DIR"
            exit 1
        fi
    fi

    log_info "All requirements met"
}

download_base_image() {
    log_step "Downloading Raspberry Pi OS Lite..."

    mkdir -p "$WORK_DIR"
    cd "$WORK_DIR"

    if [ -f "$BASE_IMAGE_NAME" ]; then
        log_info "Base image already downloaded, skipping..."
    else
        log_info "Downloading from: $BASE_IMAGE_URL"
        wget -q --show-progress "$BASE_IMAGE_URL"
    fi

    log_step "Extracting base image..."
    xz -d -k "$BASE_IMAGE_NAME"
    BASE_IMAGE="${BASE_IMAGE_NAME%.xz}"

    log_info "Base image ready: $BASE_IMAGE"
}

mount_image() {
    log_step "Mounting image..."

    # The stock root partition has just enough room for a normal build; the
    # debug tooling (Tailscale etc.) does not fit. Grow it by 1G for --debug
    # only. Pi OS still expands root to the whole card on first boot.
    if [ "$DEBUG_IMAGE" -eq 1 ]; then
        log_info "Growing root partition by 1G for debug tooling..."
        truncate -s +1G "$BASE_IMAGE"
        parted -s "$BASE_IMAGE" resizepart 2 100%
    fi

    # Set up loop device
    LOOP_DEVICE=$(sudo losetup -f --show --partscan "$BASE_IMAGE")
    log_info "Loop device: $LOOP_DEVICE"

    # Wait for partitions to appear
    sleep 2

    if [ "$DEBUG_IMAGE" -eq 1 ]; then
        # e2fsck exits 1 when it fixed something, which is fine here.
        sudo e2fsck -fy "${LOOP_DEVICE}p2" > /dev/null || [ $? -le 1 ]
        sudo resize2fs "${LOOP_DEVICE}p2" > /dev/null
    fi

    # Create mount point
    mkdir -p "$WORK_DIR/mount"

    # Mount root partition (partition 2)
    sudo mount "${LOOP_DEVICE}p2" "$WORK_DIR/mount"
    log_info "Root partition mounted"

    # Mount boot partition (partition 1)
    sudo mount "${LOOP_DEVICE}p1" "$WORK_DIR/mount/boot/firmware"
    log_info "Boot partition mounted"
}

configure_system() {
    log_step "Configuring system..."

    MOUNT_DIR="$WORK_DIR/mount"

    # Enable SSH (dual mechanism for reliability)
    log_info "Enabling SSH..."

    # Method 1: Create boot trigger file (enables via sshswitch.service)
    sudo touch "$MOUNT_DIR/boot/firmware/ssh"

    # Method 2: Enable via systemd symlink (defense in depth)
    log_info "Enabling SSH service via systemd symlink..."
    sudo mkdir -p "$MOUNT_DIR/etc/systemd/system/multi-user.target.wants"
    sudo ln -sf /lib/systemd/system/ssh.service \
        "$MOUNT_DIR/etc/systemd/system/multi-user.target.wants/ssh.service"

    # Create sshd.service alias for compatibility
    sudo ln -sf /lib/systemd/system/ssh.service \
        "$MOUNT_DIR/etc/systemd/system/sshd.service"

    log_info "SSH enabled via dual mechanisms (boot file + systemd)"

    # NOTE: The device UUID is deliberately NOT generated here.
    # A UUID written at build time is baked into the image, so every card
    # flashed from it would claim the same device identity on the server.
    # streamscene-firstboot.service runs client/first_boot.sh on each device's
    # first boot to generate a unique UUID into
    # /boot/firmware/streamscene-device.txt. Do not reinstate a build-time UUID.
    log_info "Device UUID deferred to first boot (per-device, not per-image)"

    # Ensure any UUID left over from a previous build is not shipped
    sudo rm -f "$MOUNT_DIR/boot/firmware/streamscene-device.txt"

    # Enable SPI - required by the Waveshare 7.3" e-Paper HAT
    log_info "Enabling SPI for the E Ink display..."
    BOOT_CONFIG="$MOUNT_DIR/boot/firmware/config.txt"
    if grep -qE '^\s*dtparam=spi=on' "$BOOT_CONFIG"; then
        log_info "SPI already enabled"
    elif grep -qE '^\s*#\s*dtparam=spi=on' "$BOOT_CONFIG"; then
        sudo sed -i 's|^\s*#\s*dtparam=spi=on.*|dtparam=spi=on|' "$BOOT_CONFIG"
        log_info "SPI enabled (uncommented existing dtparam)"
    else
        echo "dtparam=spi=on" | sudo tee -a "$BOOT_CONFIG" > /dev/null
        log_info "SPI enabled (appended dtparam)"
    fi

    # Set default password for pi user
    log_info "Setting default password (pi:$DEFAULT_PASSWORD)..."
    ENCRYPTED_PASSWORD=$(openssl passwd -6 "$DEFAULT_PASSWORD")
    sudo sed -i "s|^pi:[^:]*:|pi:$ENCRYPTED_PASSWORD:|" "$MOUNT_DIR/etc/shadow"

    # Enable mDNS for easy discovery
    log_info "Configuring mDNS (streamscene.local)..."
    sudo sed -i 's/^#\?MulticastDNS=.*/MulticastDNS=yes/' "$MOUNT_DIR/etc/systemd/resolved.conf" || true

    log_info "System configuration complete"
}

install_dependencies() {
    log_step "Installing dependencies via chroot..."

    MOUNT_DIR="$WORK_DIR/mount"

    # Bind-mount the kernel filesystems into the image before chrooting.
    # Package postinst scripts need them: initramfs-tools fails with
    # "MODULES dep requires mounted sysfs on /sys" and systemd-tmpfiles needs
    # /proc. Without these, apt exits non-zero, the chroot script aborts under
    # 'set -e', and everything after the package install silently never runs.
    log_info "Bind-mounting /proc, /sys, /dev, /dev/pts into the image..."
    sudo mount -t proc  proc  "$MOUNT_DIR/proc"
    sudo mount -t sysfs sysfs "$MOUNT_DIR/sys"
    sudo mount --bind /dev     "$MOUNT_DIR/dev"
    sudo mount --bind /dev/pts "$MOUNT_DIR/dev/pts"

    # Copy qemu-arm-static for chroot (if on x86_64)
    if [ "$(uname -m)" = "x86_64" ]; then
        log_info "Setting up ARM emulation..."
        sudo cp /usr/bin/qemu-arm-static "$MOUNT_DIR/usr/bin/" 2>/dev/null || {
            log_warn "qemu-arm-static not found - skipping chroot package installation"
            log_warn "You may need to install packages manually on the Pi"
            return
        }
    fi

    # Create installation script
    cat > "$WORK_DIR/install_packages.sh" << 'EOF'
#!/bin/bash
set -e
export DEBIAN_FRONTEND=noninteractive

echo "Updating package lists..."
apt-get update -qq

echo "Installing StreamScene dependencies..."
apt-get install -y -qq \
    hostapd \
    dnsmasq \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    git \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    libtiff-dev \
    libwebp-dev \
    liblcms2-dev \
    libopenjp2-7 \
    dhcpcd5 \
    isc-dhcp-client \
    rfkill

echo "Disabling dhcpcd daemon (client invokes it per-interface on demand)..."
# dhcpcd5 is installed because wifi_client.py shells out to `dhcpcd` for a DHCP
# lease - without the binary the device associates but never gets an IP.
# But its daemon must NOT auto-start: it manages every interface by default,
# so it grabs wlan0, fights the hotspot's static 192.168.4.1, and destabilises
# the AP - which clients report as "wrong password" when they fail to associate.
# NOTE: `systemctl disable` is unreliable in a chroot (no D-Bus), so remove the
# enablement symlinks directly and mask the unit. The dhcpcd BINARY stays
# available - wifi_client.py invokes it per-interface when it wants a lease.
rm -f /etc/systemd/system/multi-user.target.wants/dhcpcd.service
rm -f /etc/systemd/system/dhcpcd.service.wants/* 2>/dev/null || true
rm -f /etc/rc[0-9S].d/S[0-9][0-9]dhcpcd
ln -sf /dev/null /etc/systemd/system/dhcpcd.service
echo "dhcpcd daemon disabled and masked; binary remains at $(command -v dhcpcd || echo /usr/sbin/dhcpcd)"

echo "Disabling hostapd and dnsmasq auto-start..."
systemctl disable hostapd
systemctl disable dnsmasq

echo "Disabling NetworkManager (conflicts with manual network control)..."
systemctl disable NetworkManager 2>/dev/null || true
systemctl mask NetworkManager 2>/dev/null || true

echo "Setting Python capabilities for port 80 binding..."
setcap 'cap_net_bind_service=+ep' /usr/bin/python3.11 || setcap 'cap_net_bind_service=+ep' /usr/bin/python3 || true

echo "Package installation complete"
EOF

    chmod +x "$WORK_DIR/install_packages.sh"
    sudo cp "$WORK_DIR/install_packages.sh" "$MOUNT_DIR/tmp/"

    # Run installation in chroot
    log_info "Installing packages (this may take a few minutes)..."
    CHROOT_STATUS=0
    sudo chroot "$MOUNT_DIR" /tmp/install_packages.sh || CHROOT_STATUS=$?

    # Release the kernel filesystems as soon as the chroot is done.
    sudo umount "$MOUNT_DIR/dev/pts" 2>/dev/null || true
    sudo umount "$MOUNT_DIR/dev"     2>/dev/null || true
    sudo umount "$MOUNT_DIR/sys"     2>/dev/null || true
    sudo umount "$MOUNT_DIR/proc"    2>/dev/null || true

    # A failed package install must stop the build. The old behaviour - warn and
    # claim "packages will install on first boot" - is not survivable: the device
    # has no network until the captive portal runs, and the portal is Python that
    # needs those very packages.
    if [ $CHROOT_STATUS -ne 0 ]; then
        log_error "Chroot package installation failed (exit $CHROOT_STATUS) - aborting."
        exit 1
    fi
    true || {
        log_warn "Chroot package installation failed - packages will install on first boot"
    }

    # Cleanup
    sudo rm -f "$MOUNT_DIR/tmp/install_packages.sh"
    if [ "$(uname -m)" = "x86_64" ]; then
        sudo rm -f "$MOUNT_DIR/usr/bin/qemu-arm-static"
    fi

    log_info "Dependencies installed"
}

install_client() {
    log_step "Installing StreamScene client..."

    MOUNT_DIR="$WORK_DIR/mount"
    CLIENT_INSTALL_DIR="$MOUNT_DIR/home/pi/streamscene-client"

    # Create client directory
    sudo mkdir -p "$CLIENT_INSTALL_DIR"

    # Copy client files
    log_info "Copying client code..."
    sudo cp -r "$CLIENT_DIR"/* "$CLIENT_INSTALL_DIR/"

    # Create virtual environment and install Python dependencies in chroot
    log_info "Creating Python virtual environment and installing dependencies..."
    log_info "This may take 5-10 minutes (compiling Pillow, etc.)..."

    # NOTE: this must be fatal, not a warning. A device that ships without a
    # populated venv cannot repair itself: pip needs the network, and the
    # device has no network until the captive portal runs - which is itself
    # Python code that needs the venv. Shipping a broken venv bricks the setup
    # flow, so a failure here has to stop the build.
    # 'set -e' inside the chroot is required: without it a failing pip is
    # masked by the exit status of the following command.
    sudo chroot "$MOUNT_DIR" /bin/bash -c "
        set -e
        cd /home/pi/streamscene-client
        python3 -m venv venv
        source venv/bin/activate
        pip install --upgrade pip
        pip install -r requirements.txt
    " || {
        log_error "Python venv setup failed in chroot"
        log_error "The image cannot provision itself without a working venv - aborting."
        exit 1
    }

    # Verify the venv actually contains what the client imports at runtime.
    # pip can exit non-zero after a partial install, and a missing module here
    # only surfaces as a crash on the user's device.
    log_info "Verifying client dependencies inside the image..."
    # Import only - do not introspect __version__, which not every package
    # defines (qrcode 8.x does not) and which is not what we are testing.
    # ---------------------------------------------------------------------
    # DEV ONLY: pre-seed WiFi credentials
    #
    # Opt-in, off by default. Set DEV_WIFI_SSID and DEV_WIFI_PSK to skip the
    # hotspot/captive-portal step so a bench device joins WiFi straight away.
    #
    # NEVER use this for a device you hand to somebody else: the image would
    # carry your WiFi password in plaintext, and the recipient could not run
    # the setup flow on their own network. Distribution images must be built
    # with these variables unset. The output filename is marked accordingly so
    # a dev image cannot be mistaken for a shippable one.
    # ---------------------------------------------------------------------
    if [ -n "${DEV_WIFI_SSID:-}" ]; then
        if [ -z "${DEV_WIFI_PSK:-}" ]; then
            log_error "DEV_WIFI_SSID set without DEV_WIFI_PSK - aborting"
            exit 1
        fi
        log_warn "============================================================"
        log_warn "DEV IMAGE: pre-seeding WiFi credentials for '${DEV_WIFI_SSID}'"
        log_warn "This image contains a plaintext WiFi password."
        log_warn "DO NOT DISTRIBUTE IT."
        log_warn "============================================================"
        printf '{\n  "ssid": "%s",\n  "password": "%s",\n  "configured": true\n}\n' \
            "$DEV_WIFI_SSID" "$DEV_WIFI_PSK" \
          | sudo tee "$CLIENT_INSTALL_DIR/wifi_credentials.json" > /dev/null
        sudo chmod 600 "$CLIENT_INSTALL_DIR/wifi_credentials.json"
    else
        # Guard against a stale file surviving from a previous dev build
        sudo rm -f "$CLIENT_INSTALL_DIR/wifi_credentials.json"
        log_info "No WiFi pre-seeded (distribution build)"
    fi

    # The checks live in scripts/verify_image.py rather than inline, so the
    # quoting stays sane and the same checks can be run by hand against a
    # mounted image.
    sudo cp "$SCRIPT_DIR/scripts/verify_image.py" "$MOUNT_DIR/tmp/verify_image.py"
    # 'if' rather than '$?': under 'set -e' a bare failing command would abort
    # the script before the status could be inspected and reported.
    if sudo chroot "$MOUNT_DIR" /bin/bash -c \
        "cd /home/pi/streamscene-client && ./venv/bin/python3 /tmp/verify_image.py"; then
        VERIFY_STATUS=0
    else
        VERIFY_STATUS=1
    fi
    sudo rm -f "$MOUNT_DIR/tmp/verify_image.py"
    if [ $VERIFY_STATUS -ne 0 ]; then
        log_error "Image verification failed - aborting."
        exit 1
    fi

    # Make scripts executable
    sudo chmod +x "$CLIENT_INSTALL_DIR"/*.sh 2>/dev/null || true

    # Set ownership
    sudo chown -R 1000:1000 "$CLIENT_INSTALL_DIR"

    log_info "Client code installed"
}

install_configurations() {
    log_step "Installing system configurations..."

    MOUNT_DIR="$WORK_DIR/mount"

    # Install sudoers configuration
    log_info "Installing sudoers configuration..."
    sudo install -m 0440 "$CONFIG_DIR/sudoers.streamscene" "$MOUNT_DIR/etc/sudoers.d/streamscene"

    # Install logrotate configuration
    log_info "Installing logrotate configuration..."
    sudo install -m 0644 "$CONFIG_DIR/logrotate.streamscene" "$MOUNT_DIR/etc/logrotate.d/streamscene"

    # Force dhcpcd to recognize wlan0 as wireless. Without this, dhcpcd
    # doesn't reliably see wlan0's carrier state after wpa_supplicant
    # associates - `dhcpcd -1` hangs for its full timeout and returns
    # nothing even though association completed in ~2s. See
    # config/dhcpcd-wlan0.conf for the documented references.
    log_info "Configuring dhcpcd wireless recognition for wlan0..."
    cat "$CONFIG_DIR/dhcpcd-wlan0.conf" | sudo tee -a "$MOUNT_DIR/etc/dhcpcd.conf" > /dev/null

    # Create log directory
    log_info "Creating log directory..."
    sudo mkdir -p "$MOUNT_DIR/var/log/streamscene"
    sudo chown 1000:1000 "$MOUNT_DIR/var/log/streamscene"

    # OTA state lives in /var/lib/streamscene/ota (client/config.py). The
    # client runs as pi and cannot create it under root-owned /var/lib, so
    # every update check and state save failed with EACCES.
    log_info "Creating OTA state directory..."
    sudo mkdir -p "$MOUNT_DIR/var/lib/streamscene"
    sudo chown 1000:1000 "$MOUNT_DIR/var/lib/streamscene"

    log_info "System configurations installed"
}

install_systemd_services() {
    log_step "Installing systemd services..."

    MOUNT_DIR="$WORK_DIR/mount"

    # Install StreamScene client service
    log_info "Installing streamscene-client.service..."
    sudo cp "$CLIENT_DIR/streamscene-client.service" "$MOUNT_DIR/etc/systemd/system/"

    # Strip development-only settings from the shipped unit.
    # STREAMSCENE_ALLOW_ETHERNET is for the bench rig (Pi on a USB ethernet
    # adapter); production devices are WiFi-only and must run the hotspot and
    # captive portal setup flow. The source file keeps it for local dev.
    log_info "Removing dev-only ethernet flag from shipped service..."
    sudo sed -i 's|^Environment="STREAMSCENE_ALLOW_ETHERNET=true"|# Environment="STREAMSCENE_ALLOW_ETHERNET=true"  # dev only - stripped at build|' \
        "$MOUNT_DIR/etc/systemd/system/streamscene-client.service"

    # Install first boot provisioning service
    log_info "Installing streamscene-firstboot.service..."
    sudo cp "$CLIENT_DIR/streamscene-firstboot.service" "$MOUNT_DIR/etc/systemd/system/"

    # Enable StreamScene services (will start on boot)
    log_info "Enabling streamscene-firstboot.service..."
    sudo ln -sf /etc/systemd/system/streamscene-firstboot.service \
        "$MOUNT_DIR/etc/systemd/system/multi-user.target.wants/streamscene-firstboot.service"

    log_info "Enabling streamscene-client.service..."
    sudo ln -sf /etc/systemd/system/streamscene-client.service \
        "$MOUNT_DIR/etc/systemd/system/multi-user.target.wants/streamscene-client.service"

    log_info "Systemd services installed and enabled"
}

install_debug_tooling() {
    log_step "Installing DEBUG tooling (this image must never be distributed)..."

    MOUNT_DIR="$WORK_DIR/mount"
    local R="$MOUNT_DIR"
    local WANTS="$R/etc/systemd/system/multi-user.target.wants"

    # Packages: Tailscale (its own apt repo) and journal-upload.
    sudo mount -t proc  proc  "$R/proc"
    sudo mount -t sysfs sysfs "$R/sys"
    sudo mount --bind /dev     "$R/dev"
    sudo mount --bind /dev/pts "$R/dev/pts"
    if [ "$(uname -m)" = "x86_64" ]; then
        sudo cp /usr/bin/qemu-arm-static "$R/usr/bin/"
    fi
    cat > "$WORK_DIR/install_debug.sh" << 'EOF'
#!/bin/bash
set -e
export DEBIAN_FRONTEND=noninteractive
curl -fsSL https://pkgs.tailscale.com/stable/raspbian/bookworm.noarmor.gpg \
    -o /usr/share/keyrings/tailscale-archive-keyring.gpg
curl -fsSL https://pkgs.tailscale.com/stable/raspbian/bookworm.tailscale-keyring.list \
    -o /etc/apt/sources.list.d/tailscale.list
apt-get update -qq
apt-get install -y -qq tailscale systemd-journal-remote
apt-get clean
EOF
    sudo install -m 0755 "$WORK_DIR/install_debug.sh" "$R/tmp/install_debug.sh"
    DEBUG_STATUS=0
    sudo chroot "$R" /tmp/install_debug.sh || DEBUG_STATUS=$?
    sudo rm -f "$R/tmp/install_debug.sh"
    sudo umount "$R/dev/pts" "$R/dev" "$R/sys" "$R/proc" 2>/dev/null || true
    if [ "$(uname -m)" = "x86_64" ]; then
        sudo rm -f "$R/usr/bin/qemu-arm-static"
    fi
    if [ $DEBUG_STATUS -ne 0 ]; then
        log_error "Debug package installation failed (exit $DEBUG_STATUS) - aborting."
        exit 1
    fi

    # Root SSH, key only.
    log_info "Installing root SSH key..."
    sudo install -d -m 0700 "$R/root/.ssh"
    sudo install -m 0600 "$DEBUG_SSH_PUBKEY" "$R/root/.ssh/authorized_keys"

    # eth0 owned by systemd-networkd, out of reach of the client's dhcpcd/hotspot
    # handling. wait-online is masked: with the dongle unplugged it would stall
    # boot for two minutes.
    log_info "Handing eth0 to systemd-networkd..."
    sudo install -m 0644 "$DEBUG_DIR/eth0.network" "$R/etc/systemd/network/10-streamscene-eth0.network"
    sudo install -d "$R/etc/systemd/networkd.conf.d"
    sudo install -m 0644 "$DEBUG_DIR/networkd-foreign.conf" "$R/etc/systemd/networkd.conf.d/streamscene-debug.conf"
    sudo ln -sf /lib/systemd/system/systemd-networkd.service "$WANTS/systemd-networkd.service"
    sudo ln -sf /dev/null "$R/etc/systemd/system/systemd-networkd-wait-online.service"
    # Without resolved, networkd does not write resolv.conf. Static fallback so
    # Tailscale and journal-upload resolve while only eth0 is up; dhcpcd
    # overwrites it once wlan0 gets a lease.
    sudo rm -f "$R/etc/resolv.conf"
    printf 'nameserver 192.168.1.1\nnameserver 1.1.1.1\n' | sudo tee "$R/etc/resolv.conf" > /dev/null

    # ...and the client must not count eth0 as its network, so the real
    # hotspot/captive-portal flow runs while the bench stays reachable.
    sudo install -d "$R/etc/systemd/system/streamscene-client.service.d"
    sudo install -m 0644 "$DEBUG_DIR/client-ignore-eth0.conf" \
        "$R/etc/systemd/system/streamscene-client.service.d/debug-ignore-eth0.conf"

    log_info "Persistent journal + live upload to CT118..."
    sudo install -d "$R/var/log/journal" "$R/etc/systemd/journald.conf.d" \
        "$R/etc/systemd/journal-upload.conf.d" "$R/etc/systemd/system/systemd-journal-upload.service.d"
    sudo install -m 0644 "$DEBUG_DIR/journald-persistent.conf" "$R/etc/systemd/journald.conf.d/streamscene-debug.conf"
    sudo install -m 0644 "$DEBUG_DIR/journal-upload.conf" "$R/etc/systemd/journal-upload.conf.d/streamscene-debug.conf"
    sudo install -m 0644 "$DEBUG_DIR/journal-upload-restart.conf" \
        "$R/etc/systemd/system/systemd-journal-upload.service.d/restart.conf"
    sudo ln -sf /lib/systemd/system/systemd-journal-upload.service "$WANTS/systemd-journal-upload.service"

    log_info "Tailscale..."
    sudo install -d -m 0700 "$R/etc/streamscene-debug"
    sudo install -m 0600 "$DEBUG_TS_AUTHKEY" "$R/etc/streamscene-debug/ts-authkey"
    sudo install -m 0644 "$DEBUG_DIR/streamscene-tailscale-up.service" "$R/etc/systemd/system/"
    sudo ln -sf /lib/systemd/system/tailscaled.service "$WANTS/tailscaled.service"
    sudo ln -sf /etc/systemd/system/streamscene-tailscale-up.service "$WANTS/streamscene-tailscale-up.service"

    log_info "Heartbeat + reset-to-firstboot..."
    sudo install -m 0755 "$DEBUG_DIR/streamscene-heartbeat.sh" "$R/usr/local/sbin/streamscene-heartbeat"
    sudo install -m 0755 "$DEBUG_DIR/reset-to-firstboot" "$R/usr/local/sbin/reset-to-firstboot"
    sudo install -m 0644 "$DEBUG_DIR/streamscene-heartbeat.service" "$DEBUG_DIR/streamscene-heartbeat.timer" \
        "$R/etc/systemd/system/"
    sudo install -d "$R/etc/systemd/system/timers.target.wants"
    sudo ln -sf /etc/systemd/system/streamscene-heartbeat.timer \
        "$R/etc/systemd/system/timers.target.wants/streamscene-heartbeat.timer"
    # first_boot.sh deletes itself; keep copies so `reset-to-firstboot --full` can re-arm it.
    sudo install -d "$R/usr/local/share/streamscene-debug"
    sudo install -m 0644 "$CLIENT_DIR/first_boot.sh" "$CLIENT_DIR/streamscene-firstboot.service" \
        "$R/usr/local/share/streamscene-debug/"

    echo "streamscene-debug" | sudo tee "$R/etc/hostname" > /dev/null
    sudo sed -i 's/^127\.0\.1\.1.*/127.0.1.1\tstreamscene-debug/' "$R/etc/hosts"
    echo "debug image built from $BUILD_REV on $(date -Is)" | sudo tee "$R/etc/streamscene-debug/BUILD" > /dev/null

    for f in usr/bin/tailscale usr/lib/systemd/systemd-journal-upload root/.ssh/authorized_keys \
             etc/streamscene-debug/ts-authkey etc/systemd/network/10-streamscene-eth0.network; do
        if [ ! -e "$R/$f" ]; then
            log_error "Debug tooling missing /$f - aborting."
            exit 1
        fi
    done
    log_info "Debug tooling installed"
}

# A normal build must not contain anything from --debug.
assert_no_debug_artifacts() {
    local R="$WORK_DIR/mount"
    for f in etc/streamscene-debug root/.ssh/authorized_keys usr/local/sbin/reset-to-firstboot \
             etc/systemd/network/10-streamscene-eth0.network etc/systemd/journal-upload.conf.d; do
        if [ -e "$R/$f" ]; then
            log_error "Distribution image contains debug artifact /$f - aborting."
            exit 1
        fi
    done
    log_info "No debug artifacts present"
}

finalize_image() {
    log_step "Finalizing image..."

    MOUNT_DIR="$WORK_DIR/mount"

    # Clean up temporary files
    log_info "Cleaning up temporary files..."
    sudo rm -rf "$MOUNT_DIR/tmp/*" 2>/dev/null || true
    sudo rm -rf "$MOUNT_DIR/var/tmp/*" 2>/dev/null || true

    # Clear bash history
    sudo rm -f "$MOUNT_DIR/home/pi/.bash_history" 2>/dev/null || true

    # Unmount
    log_info "Unmounting partitions..."
    sudo umount "$MOUNT_DIR/boot/firmware"
    sudo umount "$MOUNT_DIR"

    # Detach loop device
    sudo losetup -d "$LOOP_DEVICE"
    LOOP_DEVICE=""

    # Copy to output location
    log_info "Copying image to output location..."
    sudo cp "$BASE_IMAGE" "$SCRIPT_DIR/$OUTPUT_IMAGE"

    # Calculate image size
    IMAGE_SIZE=$(du -h "$SCRIPT_DIR/$OUTPUT_IMAGE" | cut -f1)

    log_step "Image finalized: $OUTPUT_IMAGE ($IMAGE_SIZE)"
}

create_checksum() {
    log_step "Creating checksum..."

    cd "$SCRIPT_DIR"
    sha256sum "$OUTPUT_IMAGE" > "$OUTPUT_IMAGE.sha256"

    log_info "Checksum saved to: $OUTPUT_IMAGE.sha256"
}

main() {
    echo "=========================================="
    echo "StreamScene SD Card Image Builder v$VERSION"
    echo "=========================================="
    echo ""

    check_requirements
    download_base_image
    mount_image
    configure_system
    install_dependencies
    install_client
    install_configurations
    install_systemd_services
    if [ "$DEBUG_IMAGE" -eq 1 ]; then
        install_debug_tooling
    else
        assert_no_debug_artifacts
    fi
    finalize_image
    create_checksum

    echo ""
    echo -e "${GREEN}=========================================="
    echo "✓ Build Complete!"
    echo -e "==========================================${NC}"
    echo ""
    echo "Output image: $OUTPUT_IMAGE"
    echo "Image size: $(du -h "$SCRIPT_DIR/$OUTPUT_IMAGE" | cut -f1)"
    echo ""
    echo "To flash to SD card:"
    echo "  Linux:   sudo dd if=$OUTPUT_IMAGE of=/dev/sdX bs=4M status=progress"
    echo "  macOS:   sudo dd if=$OUTPUT_IMAGE of=/dev/rdiskX bs=1m"
    echo "  Windows: Use Raspberry Pi Imager or Etcher"
    echo ""
    echo "Default credentials:"
    echo "  Username: pi"
    echo "  Password: $DEFAULT_PASSWORD"
    echo "  SSH: Enabled"
    echo ""
    echo "After flashing:"
    echo "1. Insert SD card into Raspberry Pi Zero 2 WH"
    echo "2. Power on - device will provision automatically"
    echo "3. Connect to StreamScene-XXXX WiFi hotspot"
    echo "4. Configure WiFi via captive portal (192.168.4.1)"
    echo "5. Device will connect to WiFi and display QR code"
    echo "6. Scan QR code to register device"
    echo ""
    if [ "$DEBUG_IMAGE" -eq 1 ]; then
        echo -e "${RED}DEBUG IMAGE - DO NOT DISTRIBUTE${NC} (root SSH key, Tailscale key, journal forwarding)"
        echo "  ssh root@streamscene-debug   (tailnet)  or root@<eth0 DHCP IP>"
        echo "  logs on CT118: journalctl -D /var/log/journal/remote -t streamscene-heartbeat"
        echo ""
    fi
}

main

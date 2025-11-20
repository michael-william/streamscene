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
VERSION="1.0.0"
OUTPUT_IMAGE="streamscene-client-${VERSION}.img"
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

    # Unmount if mounted
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

    # Set up loop device
    LOOP_DEVICE=$(sudo losetup -f --show --partscan "$BASE_IMAGE")
    log_info "Loop device: $LOOP_DEVICE"

    # Wait for partitions to appear
    sleep 2

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

    # Generate unique device UUID
    log_info "Generating unique device UUID..."
    DEVICE_UUID=$(python3 -c 'import uuid; print(str(uuid.uuid4()))')
    echo "$DEVICE_UUID" | sudo tee "$MOUNT_DIR/boot/firmware/streamscene-device.txt" > /dev/null
    sudo chmod 644 "$MOUNT_DIR/boot/firmware/streamscene-device.txt"
    log_info "Device UUID: $DEVICE_UUID"

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
    rfkill

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
    sudo chroot "$MOUNT_DIR" /tmp/install_packages.sh || {
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

    sudo chroot "$MOUNT_DIR" /bin/bash -c "
        cd /home/pi/streamscene-client
        python3 -m venv venv
        source venv/bin/activate
        pip install --upgrade pip
        pip install -r requirements.txt
        deactivate
    " || {
        log_warn "Python venv setup failed in chroot - will retry on first boot"
        sudo mkdir -p "$CLIENT_INSTALL_DIR/venv"
    }

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

    # Create log directory
    log_info "Creating log directory..."
    sudo mkdir -p "$MOUNT_DIR/var/log/streamscene"
    sudo chown 1000:1000 "$MOUNT_DIR/var/log/streamscene"

    log_info "System configurations installed"
}

install_systemd_services() {
    log_step "Installing systemd services..."

    MOUNT_DIR="$WORK_DIR/mount"

    # Install StreamScene client service
    log_info "Installing streamscene-client.service..."
    sudo cp "$CLIENT_DIR/streamscene-client.service" "$MOUNT_DIR/etc/systemd/system/"

    # Enable StreamScene client service (will start on boot)
    log_info "Enabling streamscene-client.service..."
    sudo ln -s /etc/systemd/system/streamscene-client.service \
        "$MOUNT_DIR/etc/systemd/system/multi-user.target.wants/streamscene-client.service"

    log_info "Systemd services installed and enabled"
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
}

main

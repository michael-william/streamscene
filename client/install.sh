#!/bin/bash
# StreamScene Client Installation Script
# Run this on a fresh Raspberry Pi to set up the StreamScene client
#
# Usage: ./install.sh

set -e

echo "=========================================="
echo "StreamScene Client Installation"
echo "=========================================="
echo ""

# Check if running as correct user
if [ "$USER" != "badgy" ] && [ "$USER" != "pi" ]; then
    echo "⚠ Warning: This script should be run as the 'badgy' or 'pi' user"
    echo "  Current user: $USER"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

INSTALL_USER=$(whoami)
INSTALL_DIR="$HOME/streamscene-client"

echo "Installation Configuration:"
echo "  User: $INSTALL_USER"
echo "  Directory: $INSTALL_DIR"
echo ""

# Step 1: Install system dependencies
echo "Step 1: Installing System Dependencies"
echo "---------------------------------------"
sudo apt-get update
sudo apt-get install -y \
    hostapd \
    dnsmasq \
    python3-pip \
    python3-venv \
    python3-dev \
    git

# Disable services (manual control by client)
sudo systemctl disable hostapd dnsmasq || true
sudo systemctl stop hostapd dnsmasq || true

# Disable NetworkManager (prevents conflicts with manual network control)
echo "Disabling NetworkManager..."
sudo systemctl disable NetworkManager 2>/dev/null || true
sudo systemctl mask NetworkManager 2>/dev/null || true
sudo systemctl stop NetworkManager 2>/dev/null || true

# Set Python capabilities for port 80 binding (captive portal)
echo "Setting Python capabilities for port 80..."
sudo setcap 'cap_net_bind_service=+ep' /usr/bin/python3.11 2>/dev/null || \
sudo setcap 'cap_net_bind_service=+ep' /usr/bin/python3 || true

echo "✓ System dependencies installed"
echo ""

# Step 2: Create directory and set permissions
echo "Step 2: Setting Up Directory"
echo "-----------------------------"
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# Ensure correct ownership
sudo chown -R $INSTALL_USER:$INSTALL_USER "$INSTALL_DIR"

echo "✓ Directory created: $INSTALL_DIR"
echo ""

# Step 3: Create Python virtual environment
echo "Step 3: Creating Python Environment"
echo "------------------------------------"
if [ -d "venv" ]; then
    echo "⚠ Virtual environment already exists, skipping..."
else
    python3 -m venv venv
    echo "✓ Virtual environment created"
fi

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

echo "✓ Python environment ready"
echo ""

# Step 4: Install Python dependencies
echo "Step 4: Installing Python Packages"
echo "-----------------------------------"

# Check if requirements.txt exists
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    # Install minimal required packages
    echo "⚠ requirements.txt not found, installing minimal dependencies..."
    pip install \
        pillow \
        requests \
        qrcode[pil]
fi

echo "✓ Python packages installed"
echo ""

# Step 5: Configure environment
echo "Step 5: Configuring Environment"
echo "--------------------------------"

# Create environment file
cat > ~/.streamscene_env << 'ENVEOF'
# StreamScene Production Configuration
export STREAMSCENE_API_URL="https://streamscene.dataandstories.com"
export STREAMSCENE_DISPLAY_MODE="headless"
ENVEOF

# Add to .bashrc if not already there
if ! grep -q "source ~/.streamscene_env" ~/.bashrc; then
    echo "" >> ~/.bashrc
    echo "# StreamScene environment" >> ~/.bashrc
    echo "[ -f ~/.streamscene_env ] && source ~/.streamscene_env" >> ~/.bashrc
    echo "✓ Environment added to ~/.bashrc"
else
    echo "✓ Environment already in ~/.bashrc"
fi

# Source it now
source ~/.streamscene_env

echo "✓ Environment configured"
echo "  API URL: $STREAMSCENE_API_URL"
echo ""

# Step 6: Set file permissions
echo "Step 6: Setting File Permissions"
echo "---------------------------------"

# Ensure all files are owned by the install user
sudo chown -R $INSTALL_USER:$INSTALL_USER "$INSTALL_DIR"

# Set correct permissions
chmod 755 "$INSTALL_DIR"
chmod +x *.py 2>/dev/null || true

# Create output directory with correct permissions
mkdir -p output
chmod 755 output

echo "✓ File permissions set"
echo ""

# Step 7: Verify device UUID
echo "Step 7: Checking Device UUID"
echo "-----------------------------"

UUID_FILE="/boot/firmware/streamscene-device.txt"

if [ -f "$UUID_FILE" ]; then
    DEVICE_UUID=$(cat "$UUID_FILE" | grep -oP 'DEVICE_UUID=\K.*|^[0-9a-f-]{36}$' | head -1)
    if [ -n "$DEVICE_UUID" ]; then
        echo "✓ Device UUID found: $DEVICE_UUID"
    else
        echo "✗ Device UUID file exists but is invalid"
        echo "  Run provision.sh to set up device UUID"
    fi
else
    echo "⚠ Device UUID not found at $UUID_FILE"
    echo "  Run provision.sh after installation to set up device UUID"
fi
echo ""

# Step 8: Install systemd service
echo "Step 8: Installing Systemd Service"
echo "-----------------------------------"

if [ -f "streamscene-client.service" ]; then
    # Update service file with actual paths
    sed "s|/home/pi|$HOME|g" streamscene-client.service > /tmp/streamscene-client.service
    sed -i "s|User=pi|User=$INSTALL_USER|g" /tmp/streamscene-client.service

    sudo cp /tmp/streamscene-client.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable streamscene-client

    echo "✓ Systemd service installed and enabled"
    echo "  Start with: sudo systemctl start streamscene-client"
    echo "  Status: sudo systemctl status streamscene-client"
    echo "  Logs: journalctl -u streamscene-client -f"
else
    echo "⚠ streamscene-client.service not found"
    echo "  Service will need to be installed manually"
fi
echo ""

echo "=========================================="
echo "Installation Complete!"
echo "=========================================="
echo ""
echo "Next Steps:"
echo "  1. Run provision.sh to set device UUID (if not done)"
echo "  2. Start the service: sudo systemctl start streamscene-client"
echo "  3. Check logs: journalctl -u streamscene-client -f"
echo "  4. Register device via web UI"
echo ""
echo "Configuration:"
echo "  Install Directory: $INSTALL_DIR"
echo "  API URL: $STREAMSCENE_API_URL"
echo "  User: $INSTALL_USER"
echo ""

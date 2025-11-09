#!/bin/bash
# Deploy StreamScene client to Raspberry Pi
# Usage: ./deploy_to_pi.sh

set -e

PI_HOST="badgy@streamscene.local"
PI_DIR="~/streamscene-client"

echo "🚀 StreamScene Client Deployment Script"
echo "========================================="
echo ""

# Create deployment archive
echo "📦 Creating deployment package..."
cd /root/streamscene
tar czf /tmp/streamscene-client.tar.gz \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='output' \
  -C client .

echo "✅ Package created: $(du -h /tmp/streamscene-client.tar.gz | cut -f1)"
echo ""

# Transfer to Pi
echo "📤 Transferring to Raspberry Pi..."
scp /tmp/streamscene-client.tar.gz ${PI_HOST}:/tmp/

echo "✅ Transfer complete"
echo ""

# Extract on Pi
echo "📂 Extracting on Raspberry Pi..."
ssh ${PI_HOST} "mkdir -p ${PI_DIR} && cd ${PI_DIR} && tar xzf /tmp/streamscene-client.tar.gz && rm /tmp/streamscene-client.tar.gz"

echo "✅ Extraction complete"
echo ""

# Verify deployment
echo "🔍 Verifying deployment..."
ssh ${PI_HOST} "ls -lh ${PI_DIR}"

echo ""
echo "✅ Deployment successful!"
echo ""
echo "Next steps:"
echo "  1. SSH into Pi: ssh ${PI_HOST}"
echo "  2. Install dependencies: sudo apt-get install -y hostapd dnsmasq"
echo "  3. Run setup: cd ~/streamscene-client && sudo python3 test_wifi_setup.py"

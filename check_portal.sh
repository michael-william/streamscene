#!/bin/bash
# Quick script to check portal server status

echo "=== Portal Server Diagnostic ==="
echo ""

echo "1. Check if anything is listening on port 80:"
sudo netstat -tlnp | grep :80 || echo "  Nothing listening on port 80"
echo ""

echo "2. Check Python binary capabilities:"
which python3
getcap $(which python3)
echo ""

echo "3. Check if the virtual env Python has capabilities:"
if [ -f ~/streamscene-client/venv/bin/python3.11 ]; then
    getcap ~/streamscene-client/venv/bin/python3.11
else
    echo "  Virtual env not found at ~/streamscene-client/venv"
fi
echo ""

echo "4. Check if main.py is running:"
ps aux | grep main.py | grep -v grep || echo "  main.py not running"
echo ""

echo "5. Try to access portal locally:"
curl -I http://192.168.4.1 2>&1 | head -5
echo ""

echo "6. Check recent logs:"
journalctl -n 20 --no-pager | grep -i "portal\|captive\|port 80"

#!/bin/bash
# Rollback to the original C++ DisplayNixie clock
# Run this on the Pi if the new Python web version has issues

set -e

echo "=== Rolling back to C++ DisplayNixie ==="

# Stop the new web service if running
sudo systemctl stop nixie-web.service 2>/dev/null || true
sudo systemctl disable nixie-web.service 2>/dev/null || true

# Restore the original binary from backup
if [ -f /home/pi/NixieClockRaspberryPi/DisplayNixie/bin/DisplayNixie-v2.3.2-backup ]; then
    cp /home/pi/NixieClockRaspberryPi/DisplayNixie/bin/DisplayNixie-v2.3.2-backup \
       /home/pi/NixieClockRaspberryPi/DisplayNixie/bin/DisplayNixie
    echo "Binary restored from backup."
fi

# Re-enable and start the original service
sudo systemctl enable nixie.service
sudo systemctl start nixie.service

echo "=== Rollback complete ==="
sudo systemctl status nixie.service

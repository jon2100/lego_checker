#!/bin/bash

echo "=== LEGO Stock Checker Setup (Advanced) ==="

# Install system packages
echo "Installing dependencies..."
sudo apt update
sudo apt install -y python3-bs4

# Install cloudscraper (not in apt repos)
echo "Installing cloudscraper..."
pip3 install cloudscraper --break-system-packages

# Create config file if it doesn't exist
if [ ! -f lego-config.ini ]; then
    cat > lego-config.ini << 'CONFIGEOF'
[email]
recipient = jdhwiz@gmail.com
smtp_server = localhost
from_address = lego-checker@localhost

[settings]
check_delay = 3
timeout = 30
CONFIGEOF
    echo "✓ Created lego-config.ini"
else
    echo "✓ lego-config.ini already exists"
fi

# Create URL file if it doesn't exist
if [ ! -f lego-urls.txt ]; then
    cat > lego-urls.txt << 'URLEOF'
# LEGO Product URLs to Monitor
# Add one URL per line
# Lines starting with # are comments

# The Globe
https://www.lego.com/en-us/product/the-globe-21332

URLEOF
    echo "✓ Created lego-urls.txt"
else
    echo "✓ lego-urls.txt already exists"
fi

# Make script executable
chmod +x lego-checker-advanced.py

# Test modules
echo ""
echo "Testing Python modules..."
if python3 -c "import cloudscraper; import bs4; print('✓ All modules available')" 2>/dev/null; then
    echo "✓ Dependencies OK"
else
    echo "✗ Missing dependencies"
    exit 1
fi

# Test run
echo ""
echo "Running test check..."
python3 lego-checker-advanced.py

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Files created:"
echo "  - lego-config.ini (email and settings)"
echo "  - lego-urls.txt (products to monitor)"
echo ""
echo "Usage:"
echo "  Edit products: nano lego-urls.txt"
echo "  Edit settings: nano lego-config.ini"
echo "  Run manually:  python3 lego-checker-advanced.py"
echo ""
echo "To add to cron (runs every hour):"
echo "  crontab -e"
echo "  Add line: 0 * * * * cd $(pwd) && python3 lego-checker-advanced.py >> /tmp/lego-checker.log 2>&1"

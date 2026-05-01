#!/bin/bash
# Quotex Web Dashboard - Linux Start Script
# This script handles the virtual environment and starts the bot.

# Ensure we're in the correct directory
cd "$(dirname "$0")" || exit

echo "=========================================================="
echo "    QUOTEX WEB DASHBOARD - LINUX STARTUP SETUP"
echo "=========================================================="

# 1. Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "[*] Setting up isolated Python Virtual Environment..."
    if ! command -v python3 &> /dev/null; then
        echo "[!] Python3 is not installed. Please install python3 and python3-venv first."
        exit 1
    fi
    python3 -m venv venv
    echo "[+] Virtual environment created."
fi

# 2. Activate the virtual environment
echo "[*] Activating virtual environment..."
source venv/bin/activate

# 3. Ensure dependencies are installed
echo "[*] Checking and installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# 4. Run the application
echo ""
echo "=========================================================="
echo " [*] Booting Quotex Web Dashboard (Premium Signal Generator)..."
echo "=========================================================="
python app_premium.py

# In case the bot terminates
echo "=========================================================="
echo " [*] Dashboard Process Exited."
deactivate

#!/bin/bash
# PEPE Scalping Bot - Auto-restart script for Mac/Linux

echo "========================================"
echo "PEPE Scalping Bot - Auto-restart Mode"
echo "========================================"
echo ""

# Change to script directory
cd "$(dirname "$0")"

# Activate virtual environment if exists
if [ -f "venv/bin/activate" ]; then
    echo "[*] Activating virtual environment..."
    source venv/bin/activate
fi

while true; do
    echo ""
    echo "[*] Starting bot..."
    echo "[*] Press Ctrl+C to stop"
    echo ""

    # Run the bot
    python src/main.py
    EXIT_CODE=$?

    if [ $EXIT_CODE -eq 0 ]; then
        echo ""
        echo "[*] Bot stopped gracefully."
        break
    fi

    echo ""
    echo "[!] Bot crashed with exit code: $EXIT_CODE"
    echo "[*] Restarting in 5 seconds..."
    echo "[*] Press Ctrl+C to cancel restart"

    sleep 5
done

echo ""
echo "[*] Script ended."

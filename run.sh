#!/usr/bin/env bash
# run.sh — quick-start script for Site Data Analysis app
#
# WHERE TO RUN THIS:
#   On your own computer. Open a terminal in this project folder and run:
#       bash run.sh
#   Then open  http://localhost:8080  in your browser.
set -e

echo "Installing dependencies..."
pip install -r requirements.txt -q

echo ""
echo "============================================="
echo "  App starting at  http://localhost:8080"
echo "  Open that URL in your browser."
echo "  Press Ctrl+C to stop."
echo "============================================="
echo ""

# Try to open the browser automatically (macOS / Linux desktop)
if command -v open &>/dev/null; then
    # macOS
    (sleep 3 && open http://localhost:8080) &
elif command -v xdg-open &>/dev/null; then
    # Linux with a desktop environment
    (sleep 3 && xdg-open http://localhost:8080) &
fi

python app.py

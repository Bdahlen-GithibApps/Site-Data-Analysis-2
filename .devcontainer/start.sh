#!/usr/bin/env bash
# start.sh — Codespaces startup script for Site Data Analysis app
# Kills any existing instance, then starts the app and logs output.

set -e

LOG=/tmp/app.log

# Kill any previous instance
pkill -f "python.*app.py" 2>/dev/null || true
sleep 1

echo "Starting Dev Code Lookup on port 8080..."
cd /workspaces/Site-Data-Analysis-2
nohup python app.py > "$LOG" 2>&1 &

# Wait up to 15 seconds for the app to be ready
for i in $(seq 1 15); do
    sleep 1
    if curl -sf http://localhost:8080 > /dev/null 2>&1; then
        echo "App is ready at http://localhost:8080"
        exit 0
    fi
done

echo "WARNING: app may not have started. Check $LOG for errors."
cat "$LOG"

#!/usr/bin/env bash
# run.sh — quick-start script for Site Data Analysis app
set -e

echo "Installing dependencies..."
pip install -r requirements.txt

echo ""
echo "Starting app at http://localhost:8080 ..."
echo "Press Ctrl+C to stop."
echo ""
python app.py

#!/bin/bash

# Kill any running instance
pkill -f "python app.py" 2>/dev/null
while pgrep -f "python app.py" >/dev/null; do
    sleep 0.2
done

source .venv/bin/activate
nohup python app.py > /dev/null 2>&1 &

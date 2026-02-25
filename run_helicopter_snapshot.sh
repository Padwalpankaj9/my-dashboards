#!/bin/zsh
# Generate latest visibility snapshot for helicopter dashboard.
cd /Users/apple/Documents/my-dashboards || exit 1
/opt/homebrew/bin/python3 scripts_generate_helicopter_snapshot.py

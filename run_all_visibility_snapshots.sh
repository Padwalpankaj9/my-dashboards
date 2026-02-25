#!/bin/zsh
# Generate all visibility snapshots for dashboards.
cd /Users/apple/Documents/my-dashboards || exit 1
/opt/homebrew/bin/python3 scripts_generate_helicopter_snapshot.py
/opt/homebrew/bin/python3 scripts_generate_control_tower_snapshot.py

#!/bin/bash

uv pip list --outdated --format json \
  | python3 -c "
import json, sys, tomllib

with open('pyproject.toml', 'rb') as f:
    direct = {d.split('[')[0].split('~')[0].split('>')[0].split('<')[0].split('=')[0].strip().lower()
              for d in tomllib.load(f)['project']['dependencies']}

outdated = json.load(sys.stdin)
for pkg in outdated:
    if pkg['name'].lower() in direct:
        print(f\"{pkg['name']}: {pkg['version']} -> {pkg['latest_version']}\")
"

#!/bin/sh
# Compatibility entrypoint; configuration is parsed as data by deploy.py.
set -eu
cd "$(dirname "$0")/.."
exec python3 scripts/deploy.py provision "$@"

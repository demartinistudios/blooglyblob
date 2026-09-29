#!/bin/sh
# Explicit contributor setup; never called by offline checks.
set -eu
cd "$(dirname "$0")/../../.."
if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
    echo "Install Node.js 22 or newer with npm, then rerun make guide-setup." >&2
    exit 2
fi
node -e 'if (Number(process.versions.node.split(".")[0]) < 22) { console.error("Node.js 22 or newer is required."); process.exit(2); }'
case "${GUIDE_SYSTEM_DEPS:-0}" in
    0) set -- chromium ;;
    1) set -- --with-deps chromium ;;
    *) echo "GUIDE_SYSTEM_DEPS must be 0 or 1." >&2; exit 2 ;;
esac
npm ci --ignore-scripts --prefix hardware/tools/guide
hardware/tools/guide/node_modules/.bin/playwright install "$@"

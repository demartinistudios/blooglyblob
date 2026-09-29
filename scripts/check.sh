#!/bin/sh
# One contributor check definition, used by Make and CI.
set -eu
cd "$(dirname "$0")/.."
python="${DEV_PYTHON:-.venv/bin/python}"
if ! command -v "$python" >/dev/null 2>&1; then
    echo "Missing Python: $python. Run make dev-setup HOST_PYTHON=python3.12 first." >&2
    exit 2
fi
if [ "$#" -eq 0 ]; then
    set -- format-check lint typecheck test
fi
for check in "$@"; do
    case "$check" in
        format|format-check|lint) module=ruff ;;
        typecheck) module=mypy ;;
        test) module=pytest ;;
        coverage) module=coverage ;;
        *) echo "Unknown check: $check (choose format, format-check, lint, typecheck, test, coverage)" >&2; exit 2 ;;
    esac
    if ! "$python" -c "import importlib.util, sys; sys.exit(importlib.util.find_spec('$module') is None)"; then
        echo "Missing $module in $python. Run make dev-setup first." >&2
        exit 2
    fi
    echo "Checking: $check"
    case "$check" in
        format) "$python" -m ruff format blooglyblob scripts tests ;;
        format-check) "$python" -m ruff format --check blooglyblob scripts tests ;;
        lint) "$python" -m ruff check blooglyblob scripts tests ;;
        typecheck) "$python" -m mypy blooglyblob scripts/deploy.py scripts/device_install.py ;;
        test) "$python" -m pytest tests/ -q ;;
        coverage)
            "$python" -m coverage run -m pytest tests/ -q
            "$python" -m coverage report
            "$python" -m coverage xml
            ;;
    esac
done

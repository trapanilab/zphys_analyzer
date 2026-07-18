#!/bin/zsh
set -e

cd "$(dirname "$0")/.."

echo "Installing zPhys in a local .venv environment..."
echo ""

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 was not found."
  echo ""
  echo "Install Python first, then run this script again."
  echo "Recommended for most Macs: https://www.python.org/downloads/macos/"
  echo "Recommended for conda users: install Miniforge, then see INSTALL.md."
  echo ""
  read "?Press Return to close."
  exit 1
fi

PYVER=$(python3 - <<'PY'
import sys
print(f"{sys.version_info.major}.{sys.version_info.minor}")
PY
)

echo "Found Python $PYVER"
python3 - <<'PY'
import sys
if sys.version_info < (3, 10):
    raise SystemExit("Python 3.10 or newer is required. Please install Python 3.11 or 3.12.")
PY

python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e .

echo ""
echo "zPhys installation complete."
echo "To start the app, double-click scripts/run_mac.command"
echo ""
read "?Press Return to close."

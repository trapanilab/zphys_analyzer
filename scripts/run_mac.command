#!/bin/zsh
set -e

cd "$(dirname "$0")/.."

if [ ! -d ".venv" ]; then
  echo "zPhys has not been installed yet."
  echo "Double-click scripts/install_mac.command first."
  echo ""
  read "?Press Return to close."
  exit 1
fi

. .venv/bin/activate
python -m zphys.app

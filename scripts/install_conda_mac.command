#!/bin/zsh
set -e
cd "$(dirname "$0")/.."

if ! command -v conda >/dev/null 2>&1; then
  echo "conda was not found."
  echo "Install Miniforge first, then reopen Terminal and run this script again."
  echo "Intel Mac: https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-MacOSX-x86_64.sh"
  echo "Apple Silicon: https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-MacOSX-arm64.sh"
  read "?Press Return to close."
  exit 1
fi

conda env create -f environment.yml || conda env update -f environment.yml
echo ""
echo "Conda environment installed/updated."
echo "Run with: conda activate zphys && zphys"
read "?Press Return to close."

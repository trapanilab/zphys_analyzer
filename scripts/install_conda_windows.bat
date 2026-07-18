\
@echo off
setlocal
cd /d "%~dp0\.."

where conda >nul 2>nul
if errorlevel 1 (
    echo conda was not found.
    echo Install Miniforge first, then open a new Anaconda/Miniforge Prompt and run this script again.
    echo https://conda-forge.org/download/
    pause
    exit /b 1
)

conda env create -f environment.yml
if errorlevel 1 conda env update -f environment.yml

echo.
echo Conda environment installed/updated.
echo Run with: conda activate zphys ^&^& zphys
pause

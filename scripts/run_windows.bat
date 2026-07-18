\
@echo off
setlocal
cd /d "%~dp0\.."

if not exist ".venv\Scripts\python.exe" (
    echo zPhys has not been installed yet.
    echo Double-click scripts\install_windows.bat first.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
python -m zphys.app

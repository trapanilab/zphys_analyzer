\
@echo off
setlocal
cd /d "%~dp0\.."

echo Installing zPhys in a local .venv environment...
echo.

where py >nul 2>nul
if %errorlevel%==0 (
    set PYTHON_CMD=py -3.11
    py -3.11 --version >nul 2>nul
    if errorlevel 1 set PYTHON_CMD=py -3
) else (
    where python >nul 2>nul
    if errorlevel 1 goto NoPython
    set PYTHON_CMD=python
)

%PYTHON_CMD% -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)"
if errorlevel 1 (
    echo Python 3.10 or newer is required. Python 3.11 is recommended.
    echo Install Python from https://www.python.org/downloads/windows/
    echo IMPORTANT: check "Add python.exe to PATH" during installation.
    pause
    exit /b 1
)

%PYTHON_CMD% -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e .

echo.
echo zPhys installation complete.
echo To start the app, double-click scripts\run_windows.bat
echo.
pause
exit /b 0

:NoPython
echo Python was not found.
echo.
echo Install Python first, then run this script again:
echo https://www.python.org/downloads/windows/
echo.
echo IMPORTANT: during installation, check "Add python.exe to PATH".
echo.
pause
exit /b 1

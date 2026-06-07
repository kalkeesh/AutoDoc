@echo off
setlocal

cd /d "%~dp0"

set "PYTHON_LAUNCHER="
set "PYTHON_LAUNCHER_ARGS="

where py >nul 2>nul
if not errorlevel 1 (
    py -3.13 -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 13) else 1)" >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_LAUNCHER=py"
        set "PYTHON_LAUNCHER_ARGS=-3.13"
    )
)

if not defined PYTHON_LAUNCHER (
    where python >nul 2>nul
    if not errorlevel 1 (
        python -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 13) else 1)" >nul 2>nul
        if not errorlevel 1 (
            set "PYTHON_LAUNCHER=python"
        )
    )
)

if not defined PYTHON_LAUNCHER (
    echo Python 3.13 was not found on this laptop.
    echo Please install Python 3.13 and make sure it is added to PATH before running setup.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    "%PYTHON_LAUNCHER%" %PYTHON_LAUNCHER_ARGS% -m venv .venv
    if errorlevel 1 (
        echo Failed to create virtual environment.
        pause
        exit /b 1
    )
)

echo Upgrading pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (
    echo Failed to upgrade pip.
    pause
    exit /b 1
)

echo Installing dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to install dependencies.
    pause
    exit /b 1
)

echo Setup complete.
pause

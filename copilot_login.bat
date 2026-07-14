@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found.
    echo Running setup.bat first...
    call "%~dp0setup.bat"
    if errorlevel 1 (
        echo Setup failed. Please fix setup first, then run this file again.
        pause
        exit /b 1
    )
)

echo.
echo Preparing GitHub Copilot runtime...
".venv\Scripts\python.exe" -m copilot download-runtime
if errorlevel 1 (
    echo.
    echo Could not download the Copilot runtime.
    echo Check internet/proxy access, then run this file again.
    pause
    exit /b 1
)

echo.
echo AutoDoc can use Copilot in either of these ways:
echo   1. A GitHub token stored as COPILOT_GITHUB_TOKEN.
echo   2. An existing GitHub/Copilot login cached for this Windows user.
echo.
echo If you have a GitHub token, paste it below.
echo Leave blank and press Enter to only test existing logged-in-user auth.
echo.
set /p COPILOT_TOKEN=GitHub token:

if defined COPILOT_TOKEN (
    set "COPILOT_GITHUB_TOKEN=%COPILOT_TOKEN%"
    setx COPILOT_GITHUB_TOKEN "%COPILOT_TOKEN%" >nul
    echo.
    echo COPILOT_GITHUB_TOKEN saved for this Windows user.
    echo Close and reopen Command Prompt/AutoDoc after this if it was already open.
) else (
    echo.
    echo No token entered. Testing existing logged-in-user auth instead.
)

echo.
echo Testing Copilot authentication...
".venv\Scripts\python.exe" "copilot_auth_check.py"
if errorlevel 1 (
    echo.
    echo Copilot is still not authenticated.
    echo If you used a token, make sure it is valid and the GitHub account has Copilot access.
    echo If you left token blank, sign in with a GitHub tool on this Windows user or rerun this file with a token.
    pause
    exit /b 1
)

echo.
echo Copilot auth looks ready for AutoDoc.
pause

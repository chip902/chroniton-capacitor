@echo off
echo Calendar Sync Agent - Starting...

REM Set the path to the Python executable - update this path as needed
set PYTHON_PATH=python

REM Check if Python is installed
%PYTHON_PATH% --version 2>NUL
if %ERRORLEVEL% NEQ 0 (
    echo Python is not installed or not in PATH. Please install Python 3.7+ and try again.
    pause
    exit /b 1
)

REM Check if required packages are installed
%PYTHON_PATH% -c "import win32com.client, aiohttp" 2>NUL
if %ERRORLEVEL% NEQ 0 (
    echo Installing required packages...
    %PYTHON_PATH% -m pip install pywin32 aiohttp
)

REM Set the API URL to your central calendar service
set API_URL=http://your-central-service:8000

echo Starting Calendar Sync Agent...
%PYTHON_PATH% remote_agent.py --config outlook_config.json --central-api %API_URL%

REM If we get here, there was an error
echo Agent stopped unexpectedly.
pause
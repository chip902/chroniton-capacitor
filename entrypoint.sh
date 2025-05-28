#!/bin/bash
set -e

# Print Python version and environment info
echo "=== Python Version ==="
python --version

# Print system information
echo -e "\n=== System Information ==="
uname -a

# Generate a default SECRET_KEY if not set
if [ -z "$SECRET_KEY" ]; then
    export SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')
    echo "WARNING: SECRET_KEY was not set. Generated a temporary one."
fi

# Show environment variables (excluding sensitive ones)
echo -e "\n=== Environment Variables ==="
printenv | grep -v -E 'SECRET_KEY|PASSWORD|TOKEN|KEY|SECRET' | sort

# Show directory structure
echo -e "\n=== Directory Structure ==="
ls -la /app

# Check if source directory exists
echo -e "\n=== Checking Source Directory ==="
if [ -d "/app/src" ]; then
    echo "Source directory found at /app/src"
    ls -la /app/src
else
    echo "ERROR: Source directory /app/src not found!"
    echo "Current directory contents:"
    pwd
    ls -la .
    exit 1
fi

# Start the application
echo -e "\n=== Starting Application ==="
exec python -m uvicorn src.main:app --host 0.0.0.0 --port 8008 --reload
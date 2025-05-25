#!/bin/bash
set -e

# Print Python version
echo "Python version:"
python --version

# Print system information
echo "System information:"
uname -a

# List directories to verify content
echo "Application files:"
ls -l

# Start the application directly with Uvicorn
exec uvicorn src.main:app --host 0.0.0.0 --port 8008
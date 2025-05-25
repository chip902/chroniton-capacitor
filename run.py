#!/usr/bin/env python3
"""
Helper script to run the calendar microservice with correct Python module paths.
This script ensures the src directory is in the Python path.
"""

import os
import sys
import uvicorn

# Add the current directory to Python path to make src package discoverable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    # Run the server with proper path configuration
    uvicorn.run("src.main:app", host="0.0.0.0", port=8008, reload=True)
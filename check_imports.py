#!/usr/bin/env python
"""
Diagnostic script to check import dependencies for the sync module.
"""

import sys
import importlib
import traceback


def check_module_import(module_name):
    """Try to import a module and print status."""
    try:
        module = importlib.import_module(module_name)
        print(f"✅ Successfully imported {module_name}")
        return True
    except Exception as e:
        print(f"❌ Failed to import {module_name}: {e}")
        traceback.print_exc()
        return False


def main():
    """Check all critical imports for sync functionality."""
    print("== Checking critical imports ==")

    # Basic dependencies
    modules_to_check = [
        "aioredis",
        "redis",
        "googleapiclient",
        "google.auth",
        "fastapi",
        "pydantic",
        "json",
        "os",
        "logging",
        "typing",
        "datetime"
    ]

    # Project modules
    project_modules = [
        "utils.config",
        "sync.storage",
        "sync.controller"
    ]

    all_succeeded = True

    # Check basic dependencies
    print("\n== Checking basic dependencies ==")
    for module in modules_to_check:
        if not check_module_import(module):
            all_succeeded = False

    # Check project modules
    print("\n== Checking project modules ==")
    sys.path.append("/app")  # Ensure project modules can be found
    for module in project_modules:
        if not check_module_import(module):
            all_succeeded = False

    # Overall status
    print("\n== Overall Status ==")
    if all_succeeded:
        print("✅ All modules imported successfully")
    else:
        print("❌ Some modules failed to import")


if __name__ == "__main__":
    main()

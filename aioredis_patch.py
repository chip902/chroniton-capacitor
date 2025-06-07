"""
Patch for aioredis TimeoutError compatibility issue with Python 3.11.
This should be imported before any other imports in main.py.
"""

import sys
import logging
import importlib.util

logger = logging.getLogger(__name__)


def apply_aioredis_patch():
    """
    Apply patch to fix aioredis.exceptions.TimeoutError conflict with built-in TimeoutError.
    """
    try:
        # Check if aioredis is installed
        if importlib.util.find_spec("aioredis") is None:
            logger.warning("aioredis not installed, patch not needed")
            return

        # Apply patch only if we detect the issue
        import aioredis.exceptions
        import asyncio
        import builtins
        
        # If the TimeoutError class is already defined with both base classes, we need to fix it
        if hasattr(aioredis.exceptions, 'TimeoutError') and \
           asyncio.TimeoutError in aioredis.exceptions.TimeoutError.__bases__ and \
           builtins.TimeoutError in aioredis.exceptions.TimeoutError.__bases__:
            
            logger.info("Applying aioredis TimeoutError patch")
            
            # Create a new TimeoutError class with only one of the base classes
            # This avoids the "duplicate base class" error
            class PatchedTimeoutError(asyncio.TimeoutError, aioredis.exceptions.RedisError):
                pass
            
            # Replace the original TimeoutError with our patched version
            aioredis.exceptions.TimeoutError = PatchedTimeoutError
            logger.info("aioredis TimeoutError patched successfully")
    except Exception as e:
        logger.error(f"Failed to apply aioredis patch: {e}")

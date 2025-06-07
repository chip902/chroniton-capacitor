"""
Patch for aioredis TimeoutError compatibility issue with Python 3.11.
This module uses sys.meta_path to install an import hook that prevents the duplicate base class TimeoutError issue.
Import this module before any other imports in main.py.
"""

import sys
import logging
import importlib.util
import importlib.abc

logger = logging.getLogger(__name__)

# Flag to track if patch has been applied
_patched = False


class AioredisImportFinder(importlib.abc.MetaPathFinder):
    """Custom import finder for aioredis module to patch TimeoutError"""

    def __init__(self):
        self._original_import = __import__

    def find_spec(self, fullname, path, target=None):
        if fullname == 'aioredis.exceptions' or fullname.startswith('aioredis.'):
            # Get the original spec
            for finder in sys.meta_path:
                if finder is self:
                    continue
                spec = finder.find_spec(fullname, path, target)
                if spec is not None:
                    # Create our custom loader
                    if spec.loader and fullname == 'aioredis.exceptions':
                        original_loader = spec.loader
                        spec.loader = AioredisExceptionsLoader(original_loader)
                    return spec
        return None


class AioredisExceptionsLoader:
    """Custom loader that patches the aioredis.exceptions module"""

    def __init__(self, original_loader):
        self.original_loader = original_loader

    def create_module(self, spec):
        # Let the original loader create the module
        return self.original_loader.create_module(spec)

    def exec_module(self, module):
        # First, let the original loader execute the module
        try:
            # Instead of running the original exec_module, we'll manually control the execution
            # to intercept the TimeoutError class definition
            import asyncio
            import sys

            # Get the source code from the original module file
            spec = self.original_loader.get_resource_reader(module.__name__)
            source = None
            if hasattr(spec, 'get_source'):
                source = spec.get_source(module.__name__)

            if source:
                # Modify the source code to fix TimeoutError definition
                source_lines = source.split('\n')
                modified_source = []
                for line in source_lines:
                    # Replace the problematic TimeoutError definition
                    if 'class TimeoutError(' in line and 'asyncio.TimeoutError' in line and 'builtins.TimeoutError' in line:
                        # Use only asyncio.TimeoutError as a base class
                        line = line.replace(
                            'asyncio.TimeoutError, builtins.TimeoutError', 'asyncio.TimeoutError')
                    modified_source.append(line)

                # Compile and execute the modified code
                code = compile('\n'.join(modified_source),
                               module.__file__, 'exec')
                exec(code, module.__dict__)
                logger.info(
                    "Applied patch to aioredis.exceptions: fixed TimeoutError definition")
                return
        except Exception as e:
            logger.warning(
                f"Could not apply source-level patch: {e}. Falling back to runtime patch.")

        # If source modification failed, try the original exec_module and then patch
        self.original_loader.exec_module(module)

        # Now patch it
        try:
            import asyncio

            # Check if we're in Python 3.11+ where builtins.TimeoutError and asyncio.TimeoutError are the same
            if sys.version_info >= (3, 11) and hasattr(module, 'TimeoutError'):
                logger.info(
                    "Applying aioredis TimeoutError patch for Python 3.11+")

                # Get the RedisError class
                redis_error_class = None
                if hasattr(module, 'RedisError'):
                    redis_error_class = module.RedisError

                # Create a new TimeoutError class with only asyncio.TimeoutError as base
                if redis_error_class:
                    # Create the patched class with only asyncio.TimeoutError and RedisError
                    class PatchedTimeoutError(asyncio.TimeoutError, redis_error_class):
                        pass
                else:
                    # Create the patched class with only asyncio.TimeoutError
                    class PatchedTimeoutError(asyncio.TimeoutError):
                        pass

                # Store the original docstring and attributes
                if hasattr(module.TimeoutError, '__doc__'):
                    PatchedTimeoutError.__doc__ = module.TimeoutError.__doc__

                # Replace the TimeoutError class
                module.TimeoutError = PatchedTimeoutError
                logger.info("aioredis TimeoutError patched successfully")

        except Exception as e:
            logger.error(f"Failed to patch aioredis.exceptions: {e}")
            # Let it continue with the original module


def apply_aioredis_patch():
    """Install the import hook to patch aioredis"""
    global _patched

    if _patched:
        return

    try:
        # Install our finder at the beginning of meta_path
        finder = AioredisImportFinder()
        sys.meta_path.insert(0, finder)
        logger.info("Installed aioredis import hook")
        _patched = True
    except Exception as e:
        logger.error(f"Failed to install aioredis patch: {e}")

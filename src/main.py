#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.9"
# dependencies = [
#   "python-dotenv",
#   "fastapi",
#   "uvicorn",
#   "openai-agents",
#   "google-auth-oauthlib",
#   "google-api-python-client",
#   "msal",
#   "redis",
#   "aiohttp",
#   "aioredis",
#   "python-jose",
#   "tenacity"
# ]
# ///

import os
import sys
import asyncio
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables early
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("Environment variables loaded")
except ImportError:
    print("Warning: dotenv module not found, skipping .env loading")
except Exception as e:
    print(f"Error loading environment variables: {e}")

# Try to import agents module, handle gracefully if not available
agents_available = False
try:
    from agents.mcp.server import MCPServerStdio
    agents_available = True
    print("Agents module imported successfully")
except ImportError:
    print("Warning: agents module not found. MCP functionality will be disabled.")
except Exception as e:
    print(f"Error importing agents module: {e}")

# Import local modules with error handling
api_router = None
sync_router = None
setup_calendar_mcp_server = None
SyncStorageManager = None
CalendarSyncController = None
settings = None

try:
    from api.router import router as api_router
    print("API router imported")
except ImportError:
    try:
        from src.api.router import router as api_router
        print("API router imported with src prefix")
    except ImportError:
        print("Warning: Unable to import API router")
    except Exception as e:
        print(f"Error importing API router: {e}")

try:
    from api.sync_router import router as sync_router
    print("Sync router imported")
except ImportError:
    try:
        from src.api.sync_router import router as sync_router
        print("Sync router imported with src prefix")
    except ImportError:
        print("Warning: Unable to import sync router")
    except Exception as e:
        print(f"Error importing sync router: {e}")

try:
    from mcp.calendar_server import setup_calendar_mcp_server
    print("Calendar server setup imported")
except ImportError:
    try:
        from src.mcp.calendar_server import setup_calendar_mcp_server
        print("Calendar server setup imported with src prefix")
    except ImportError:
        print("Warning: Unable to import calendar server setup")
    except Exception as e:
        print(f"Error importing calendar server setup: {e}")

try:
    from sync.storage import SyncStorageManager
    print("Sync storage manager imported")
except ImportError:
    try:
        from src.sync.storage import SyncStorageManager
        print("Sync storage manager imported with src prefix")
    except ImportError:
        print("Warning: Unable to import sync storage manager")
    except Exception as e:
        print(f"Error importing sync storage manager: {e}")

try:
    from sync.controller import CalendarSyncController
    print("Calendar sync controller imported")
except ImportError:
    try:
        from src.sync.controller import CalendarSyncController
        print("Calendar sync controller imported with src prefix")
    except ImportError:
        print("Warning: Unable to import calendar sync controller")
    except Exception as e:
        print(f"Error importing calendar sync controller: {e}")

try:
    from utils.config import settings
    print("Settings imported")
except ImportError:
    try:
        from src.utils.config import settings
        print("Settings imported with src prefix")
    except ImportError:
        print("Warning: Unable to import settings")
    except Exception as e:
        print(f"Error importing settings: {e}")

# Remove duplicate load_dotenv call (already called above)
# Initialize FastAPI app
app = FastAPI(
    title="Calendar Integration Microservice",
    description="Microservice for integrating multiple calendar providers",
    version="1.0.0"
)

# Exception handler for application errors
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    print(f"Global exception handler caught: {exc}")
    return JSONResponse(
        status_code=500,
        content={"message": f"Internal server error: {str(exc)}"},
    )

# Configure CORS with error handling
try:
    if settings and hasattr(settings, 'CORS_ORIGINS'):
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.CORS_ORIGINS,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        print(f"CORS configured with origins: {settings.CORS_ORIGINS}")
    else:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Fallback to allow all origins
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        print("CORS configured with default settings (all origins)")
except Exception as e:
    print(f"Error configuring CORS: {e}")
    # Still add middleware with safe defaults
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Include API routers with error handling
try:
    if api_router:
        app.include_router(api_router, prefix="/api")
        print("API router included")
    else:
        print("Warning: API router not included")
except Exception as e:
    print(f"Error including API router: {e}")

try:
    if sync_router:
        app.include_router(sync_router, prefix="/api")
        print("Sync router included")
    else:
        print("Warning: Sync router not included")
except Exception as e:
    print(f"Error including sync router: {e}")

# MCP server instance (will be initialized on startup)
calendar_mcp_server = None

# Sync storage and controller instances
sync_storage = None
sync_controller = None

# Background task for periodic sync
sync_task = None

async def periodic_sync(interval_minutes: int = 60):
    """Run periodic synchronization"""
    print(f"Starting periodic sync with {interval_minutes} minute interval")
    while True:
        try:
            # Wait for the specified interval
            print(f"Waiting {interval_minutes} minutes until next sync")
            await asyncio.sleep(interval_minutes * 60)
            
            # Run synchronization
            print("Starting calendar synchronization")
            if sync_controller:
                try:
                    await sync_controller.sync_all_calendars()
                    print("Calendar synchronization completed successfully")
                except Exception as e:
                    print(f"Error during sync_all_calendars: {e}")
            else:
                print("Warning: sync_controller is not initialized, skipping sync")
        except asyncio.CancelledError:
            # Task is being cancelled, clean up and exit
            print("Periodic sync task cancelled, exiting cleanly")
            break
        except Exception as e:
            print(f"Error in periodic sync: {e}")
            # Continue with the loop after error
            # Add a short sleep to avoid tight loop in case of repeated errors
            await asyncio.sleep(60)  # Wait 1 minute before retrying after error

@app.on_event("startup")
async def startup_event():
    global calendar_mcp_server, sync_storage, sync_controller, sync_task
    
    # Initialize the Calendar MCP server if agents module is available
    if agents_available:
        try:
            calendar_mcp_server = await setup_calendar_mcp_server()
            print(f"Calendar MCP server started: {calendar_mcp_server.name}")
            
            # List available tools to verify connection
            tools = await calendar_mcp_server.list_tools()
            print(f"Found {len(tools)} tools available from Calendar MCP server")
        except Exception as e:
            print(f"Failed to initialize MCP server: {e}")
            calendar_mcp_server = None
    else:
        print("Skipping MCP server initialization as agents module is not available")
        calendar_mcp_server = None
    
    # Initialize sync storage
    if SyncStorageManager is not None:
        sync_storage = SyncStorageManager()
        await sync_storage.initialize()
        print("Sync storage initialized")
        
        # Initialize sync controller
        if CalendarSyncController is not None:
            sync_controller = CalendarSyncController(sync_storage)
            print("Sync controller initialized")
            
            # Start periodic sync task
            sync_interval = int(os.environ.get("SYNC_INTERVAL_MINUTES", "60"))
            sync_task = asyncio.create_task(periodic_sync(sync_interval))
            print(f"Periodic sync scheduled every {sync_interval} minutes")
        else:
            print("Skipping sync controller initialization as CalendarSyncController module is not available")
    else:
        print("Skipping sync storage initialization as SyncStorageManager module is not available")

@app.on_event("shutdown")
async def shutdown_event():
    # Cleanup resources
    global calendar_mcp_server, sync_storage, sync_task
    
    # Stop MCP server if it was initialized
    if calendar_mcp_server:
        try:
            await calendar_mcp_server.close()
            print("Calendar MCP server stopped")
        except Exception as e:
            print(f"Error stopping MCP server: {e}")
    
    # Cancel periodic sync task
    if sync_task:
        try:
            sync_task.cancel()
            try:
                await sync_task
            except asyncio.CancelledError:
                print("Periodic sync task cancelled")
        except Exception as e:
            print(f"Error cancelling sync task: {e}")
    
    # Close sync storage
    if sync_storage:
        try:
            await sync_storage.close()
            print("Sync storage closed")
        except Exception as e:
            print(f"Error closing sync storage: {e}")

# Route for health check
@app.get("/health")
async def health_check():
    return {"status": "ok"}

# Direct execution for development
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8008, reload=True)
"""
Simplified main application file that only focuses on loading the sync router.
For testing purposes only.
"""

import logging
import os
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="Calendar Service API", version="0.1.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Simple health check endpoint."""
    return {"status": "healthy"}

# Test sync endpoint that simulates the agent registration endpoint
@app.post("/sync/agents", tags=["Sync Test"])
async def test_agent_registration(request: Request):
    """Test endpoint that simulates agent registration."""
    try:
        agent_data = await request.json()
        agent_id = "test-agent-id-12345"  # Hard-coded test ID
        logger.info(f"Test agent registration successful for: {agent_data.get('name')}")
        return {
            "id": agent_id,
            "status": "registered",
            "message": "Agent registration successful (test endpoint)",
            "timestamp": "2025-06-07T00:00:00Z"
        }
    except Exception as e:
        logger.error(f"Error in test registration: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": f"Error: {str(e)}"}
        )

# Test heartbeat endpoint
@app.post("/sync/agents/{agent_id}/heartbeat", tags=["Sync Test"])
async def test_agent_heartbeat(agent_id: str, request: Request):
    """Test endpoint that simulates agent heartbeat."""
    try:
        heartbeat_data = await request.json()
        logger.info(f"Test heartbeat received for agent: {agent_id}")
        return {
            "status": "success",
            "agent_id": agent_id,
            "message": "Heartbeat acknowledged (test endpoint)",
            "received_data": heartbeat_data
        }
    except Exception as e:
        logger.error(f"Error in test heartbeat: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": f"Error: {str(e)}"}
        )

# Print application routes for debugging
@app.get("/debug/routes", tags=["Debug"])
async def list_routes():
    """List all registered routes for debugging."""
    routes = []
    for route in app.routes:
        routes.append({
            "path": route.path,
            "name": route.name,
            "methods": route.methods if hasattr(route, "methods") else None
        })
    return {"routes": routes}

# Startup event
@app.on_event("startup")
async def startup_event():
    """Application startup event."""
    logger.info("=== Starting Application ===")
    logger.info("Simplified test version loaded successfully")
    logger.info("Test sync endpoints available at /sync/agents and /sync/agents/{agent_id}/heartbeat")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("simplified_main:app", host="0.0.0.0", port=8008, reload=True)

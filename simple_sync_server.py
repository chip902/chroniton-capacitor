"""
Simplified Master Sync server focused only on the sync endpoints.
This server provides the necessary endpoints for the remote calendar agent without any dependencies on Redis.
"""

import logging
import os
import sys
import uuid
from datetime import datetime
from typing import Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In-memory storage for agents
agents = {}

# Create FastAPI app
app = FastAPI(title="Master Sync Server", description="Calendar Sync Master Server")

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Sync API routes
@app.post("/sync/agents", status_code=201)
async def register_agent(agent_data: dict):
    """
    Register a new calendar agent.
    """
    agent_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat()
    
    agents[agent_id] = {
        "id": agent_id,
        "name": agent_data.get("name", "Unknown Agent"),
        "version": agent_data.get("version", "1.0"),
        "location": agent_data.get("location", "Unknown"),
        "capabilities": agent_data.get("capabilities", []),
        "registered_at": timestamp,
        "last_heartbeat": timestamp
    }
    
    logger.info(f"Agent registered: {agent_id}")
    return {
        "agent_id": agent_id,
        "status": "registered",
        "timestamp": timestamp
    }

@app.post("/sync/agents/{agent_id}/heartbeat")
async def agent_heartbeat(agent_id: str, heartbeat_data: dict):
    """
    Process a heartbeat from a calendar agent.
    """
    if agent_id not in agents:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    timestamp = datetime.utcnow().isoformat()
    agents[agent_id]["last_heartbeat"] = timestamp
    
    # Update agent status and other fields from heartbeat data
    if "status" in heartbeat_data:
        agents[agent_id]["status"] = heartbeat_data["status"]
    if "metrics" in heartbeat_data:
        agents[agent_id]["metrics"] = heartbeat_data["metrics"]
    
    logger.info(f"Heartbeat received from agent: {agent_id}")
    return {
        "status": "acknowledged",
        "timestamp": timestamp
    }

@app.get("/sync/agents")
async def list_agents():
    """
    List all registered calendar agents.
    """
    return {"agents": list(agents.values())}

@app.get("/sync/agents/{agent_id}")
async def get_agent(agent_id: str):
    """
    Get information about a specific calendar agent.
    """
    if agent_id not in agents:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return agents[agent_id]

@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring.
    """
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.get("/")
async def root():
    """
    Root endpoint with basic server information.
    """
    return {
        "name": "Master Sync Server",
        "version": "1.0",
        "description": "Calendar Sync Master Server",
        "endpoints": [
            "/sync/agents",
            "/sync/agents/{agent_id}",
            "/sync/agents/{agent_id}/heartbeat",
            "/health"
        ]
    }

if __name__ == "__main__":
    port = int(os.environ.get("API_PORT", 8008))
    host = os.environ.get("API_HOST", "0.0.0.0")
    
    logger.info(f"Starting Master Sync Server on {host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")

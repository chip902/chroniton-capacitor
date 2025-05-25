"""
Synchronization API Router

This module defines the API endpoints for calendar synchronization.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Body
from typing import List, Dict, Any, Optional
import json
import uuid
from datetime import datetime

from sync.architecture import (
    SyncConfiguration, SyncSource, SyncDestination, SyncAgentConfig,
    SyncDirection, SyncFrequency, SyncMethod, ConflictResolution
)
from sync.controller import CalendarSyncController
from sync.storage import SyncStorageManager

# Create router
router = APIRouter(prefix="/sync", tags=["sync"])

# Dependency to get sync controller
async def get_sync_controller():
    """Create and initialize a sync controller"""
    storage = SyncStorageManager()
    await storage.initialize()
    controller = CalendarSyncController(storage)
    try:
        yield controller
    finally:
        await storage.close()

# Configuration endpoints
@router.get("/config")
async def get_configuration(
    controller: CalendarSyncController = Depends(get_sync_controller)
):
    """Get the current synchronization configuration"""
    try:
        config = await controller.load_configuration()
        return config.dict()
    except ValueError:
        # Return empty configuration if none exists
        return SyncConfiguration().dict()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load configuration: {str(e)}"
        )

@router.post("/config/destination")
async def configure_destination(
    destination: SyncDestination,
    controller: CalendarSyncController = Depends(get_sync_controller)
):
    """Configure the destination calendar"""
    try:
        result = await controller.configure_destination(destination)
        return result.dict()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to configure destination: {str(e)}"
        )

# Source management endpoints
@router.get("/sources")
async def list_sources(
    controller: CalendarSyncController = Depends(get_sync_controller)
):
    """List all synchronization sources"""
    try:
        config = await controller.load_configuration()
        return [source.dict() for source in config.sources]
    except ValueError:
        # Return empty list if no configuration exists
        return []
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list sources: {str(e)}"
        )

@router.post("/sources")
async def add_source(
    source: SyncSource,
    controller: CalendarSyncController = Depends(get_sync_controller)
):
    """Add a new synchronization source"""
    try:
        # Ensure the source has an ID
        if not source.id:
            source.id = str(uuid.uuid4())
        
        result = await controller.add_sync_source(source)
        return result.dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to add source: {str(e)}"
        )

@router.put("/sources/{source_id}")
async def update_source(
    source_id: str,
    updates: Dict[str, Any] = Body(...),
    controller: CalendarSyncController = Depends(get_sync_controller)
):
    """Update an existing synchronization source"""
    try:
        result = await controller.update_sync_source(source_id, updates)
        return result.dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update source: {str(e)}"
        )

@router.delete("/sources/{source_id}")
async def remove_source(
    source_id: str,
    controller: CalendarSyncController = Depends(get_sync_controller)
):
    """Remove a synchronization source"""
    try:
        await controller.remove_sync_source(source_id)
        return {"status": "success", "message": f"Source {source_id} removed"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to remove source: {str(e)}"
        )

# Agent management endpoints
@router.post("/agents")
async def add_agent(
    agent: SyncAgentConfig,
    controller: CalendarSyncController = Depends(get_sync_controller)
):
    """Add a new synchronization agent"""
    try:
        # Ensure the agent has an ID
        if not agent.id:
            agent.id = str(uuid.uuid4())
        
        result = await controller.add_sync_agent(agent)
        return result.dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to add agent: {str(e)}"
        )

@router.get("/agents")
async def list_agents(
    controller: CalendarSyncController = Depends(get_sync_controller)
):
    """List all synchronization agents"""
    try:
        config = await controller.load_configuration()
        return [agent.dict() for agent in config.agents]
    except ValueError:
        # Return empty list if no configuration exists
        return []
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list agents: {str(e)}"
        )

@router.get("/agents/status")
async def check_agent_status(
    controller: CalendarSyncController = Depends(get_sync_controller)
):
    """Check status of all synchronization agents"""
    try:
        return await controller.check_agent_heartbeats()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check agent status: {str(e)}"
        )

@router.post("/agents/{agent_id}/heartbeat")
async def agent_heartbeat(
    agent_id: str,
    data: Dict[str, Any] = Body(...),
    controller: CalendarSyncController = Depends(get_sync_controller)
):
    """Register a heartbeat from a sync agent"""
    try:
        return await controller.register_agent_heartbeat(agent_id, data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to register heartbeat: {str(e)}"
        )

# Synchronization endpoints
@router.post("/run")
async def sync_all_calendars(
    controller: CalendarSyncController = Depends(get_sync_controller)
):
    """Synchronize all calendars from all sources to the destination calendar"""
    try:
        return await controller.sync_all_calendars()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Synchronization failed: {str(e)}"
        )

@router.post("/run/{source_id}")
async def sync_single_source(
    source_id: str,
    controller: CalendarSyncController = Depends(get_sync_controller)
):
    """Synchronize a single source to the destination calendar"""
    try:
        return await controller.sync_single_source(source_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Synchronization failed: {str(e)}"
        )

# Import endpoints
@router.post("/import/{source_id}")
async def import_events(
    source_id: str,
    events: List[Dict[str, Any]] = Body(...),
    controller: CalendarSyncController = Depends(get_sync_controller)
):
    """Import events for a specific source"""
    try:
        # Store the imported events
        await controller.storage.save_import_data(source_id, events)
        
        # Trigger a sync for this source
        sync_result = await controller.sync_single_source(source_id)
        
        return {
            "status": "success",
            "events_imported": len(events),
            "sync_result": sync_result
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Import failed: {str(e)}"
        )

# Bidirectional sync endpoints for pushing changes to agents
@router.post("/push/calendar-metadata")
async def push_calendar_metadata_changes(
    changes: Dict[str, Any] = Body(...),
    target_agents: Optional[List[str]] = Body(None),
    controller: CalendarSyncController = Depends(get_sync_controller)
):
    """Push calendar metadata changes to remote agents"""
    try:
        return await controller.push_calendar_metadata_changes(changes, target_agents)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to push calendar metadata changes: {str(e)}"
        )

@router.post("/push/sync-config")
async def push_sync_configuration_updates(
    config_updates: Dict[str, Any] = Body(...),
    target_agents: Optional[List[str]] = Body(None),
    controller: CalendarSyncController = Depends(get_sync_controller)
):
    """Push sync configuration updates to remote agents"""
    try:
        return await controller.push_sync_config_updates(config_updates, target_agents)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to push sync config updates: {str(e)}"
        )

@router.post("/agents/{agent_id}/receive-updates")
async def send_updates_to_agent(
    agent_id: str,
    updates: Dict[str, Any] = Body(...),
    controller: CalendarSyncController = Depends(get_sync_controller)
):
    """Send updates directly to a specific agent"""
    try:
        return await controller.send_updates_to_agent(agent_id, updates)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to send updates to agent: {str(e)}"
        )

@router.get("/agents/{agent_id}/pending-updates")
async def get_pending_updates_for_agent(
    agent_id: str,
    controller: CalendarSyncController = Depends(get_sync_controller)
):
    """Get pending updates for a specific agent"""
    try:
        return await controller.get_pending_updates_for_agent(agent_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to get pending updates: {str(e)}"
        )

@router.post("/agents/{agent_id}/updates/{update_id}/processed")
async def mark_update_processed(
    agent_id: str,
    update_id: str,
    controller: CalendarSyncController = Depends(get_sync_controller)
):
    """Mark an update as processed by an agent"""
    try:
        return await controller.mark_agent_update_processed(agent_id, update_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to mark update as processed: {str(e)}"
        )
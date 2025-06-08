"""
Synchronization API Router

This module defines the API endpoints for calendar synchronization.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Body
from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime

from sync.architecture import (
    SyncConfiguration, SyncSource, SyncDestination, SyncAgentConfig,
    SyncDirection, SyncFrequency, SyncMethod, ConflictResolution
)
from sync.controller import CalendarSyncController
from sync.storage import SyncStorageManager
import logging

# Set up logging
logger = logging.getLogger(__name__)

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
    print(f"Heartbeat received from agent {agent_id}: {data}")  # Add this line

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


# In-memory storage for demonstration (replace with proper database)
stored_events = {}
agent_status = {}


@router.get("/health")
async def sync_health_check():
    """Check sync service health"""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "agents_registered": len(agent_status),
        "total_events": sum(len(events) for events in stored_events.values())
    }


@router.post("/agents")
async def register_agent(agent_data: Dict[str, Any] = Body(...)):
    """Register a new synchronization agent"""
    try:
        agent_id = agent_data.get("id") or str(uuid.uuid4())

        # Store agent information
        agent_status[agent_id] = {
            "id": agent_id,
            "name": agent_data.get("name", "Unknown Agent"),
            "environment": agent_data.get("environment", "Unknown"),
            "agent_type": agent_data.get("agent_type", "unknown"),
            "last_seen": datetime.utcnow().isoformat(),
            "status": "registered",
            "event_count": 0
        }

        logger.info(f"Agent registered: {agent_id} - {agent_data.get('name')}")

        return {
            "id": agent_id,
            "status": "registered",
            "message": f"Agent {agent_data.get('name')} registered successfully"
        }

    except Exception as e:
        logger.error(f"Error registering agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to register agent: {str(e)}"
        )


@router.get("/agents/status")
async def get_agents_status():
    """Get status of all registered agents"""
    return {
        "agents": list(agent_status.values()),
        "total_agents": len(agent_status),
        "active_agents": len([a for a in agent_status.values() if a.get("status") == "active"])
    }


@router.post("/agents/{agent_id}/heartbeat")
async def agent_heartbeat(agent_id: str, data: Dict[str, Any] = Body(...)):
    """Register a heartbeat from a sync agent"""
    try:
        # Update agent status
        if agent_id in agent_status:
            agent_status[agent_id].update({
                "last_seen": datetime.utcnow().isoformat(),
                "status": "active",
                "last_heartbeat_data": data
            })
        else:
            # Create new agent entry if not exists
            agent_status[agent_id] = {
                "id": agent_id,
                "name": f"Agent {agent_id}",
                "environment": data.get("environment", "Unknown"),
                "last_seen": datetime.utcnow().isoformat(),
                "status": "active",
                "event_count": 0
            }

        logger.info(f"Heartbeat received from agent {agent_id}")

        return {
            "status": "ok",
            "message": "Heartbeat received",
            "agent_status": agent_status[agent_id]
        }

    except Exception as e:
        logger.error(f"Error processing heartbeat from {agent_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to process heartbeat: {str(e)}"
        )


@router.post("/import/{agent_id}")
async def import_events(agent_id: str, events: List[Dict[str, Any]] = Body(...)):
    """Import events from a remote agent"""
    try:
        logger.info(f"Importing {len(events)} events from agent {agent_id}")

        # Validate events
        valid_events = []
        for event in events:
            if not event.get("id") or not event.get("title"):
                logger.warning(f"Skipping invalid event: {event}")
                continue

            # Ensure required fields
            event.setdefault("provider", "unknown")
            event.setdefault("calendar_id", "default")
            event.setdefault("status", "confirmed")
            event.setdefault("all_day", False)
            event.setdefault("recurring", False)
            event.setdefault("participants", [])

            # Add import metadata
            event["imported_at"] = datetime.utcnow().isoformat()
            event["imported_by_agent"] = agent_id

            valid_events.append(event)

        # Store events
        if agent_id not in stored_events:
            stored_events[agent_id] = []

        # Replace all events for this agent (full sync)
        stored_events[agent_id] = valid_events

        # Update agent status
        if agent_id in agent_status:
            agent_status[agent_id].update({
                "event_count": len(valid_events),
                "last_import": datetime.utcnow().isoformat(),
                "status": "active"
            })

        logger.info(
            f"Successfully imported {len(valid_events)} events from agent {agent_id}")

        return {
            "status": "success",
            "events_imported": len(valid_events),
            "events_skipped": len(events) - len(valid_events),
            "total_events_for_agent": len(valid_events),
            "message": f"Successfully imported {len(valid_events)} events"
        }

    except Exception as e:
        logger.error(f"Error importing events from agent {agent_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to import events: {str(e)}"
        )


@router.get("/events")
async def get_all_events(agent_id: Optional[str] = None):
    """Get all imported events, optionally filtered by agent"""
    try:
        if agent_id:
            events = stored_events.get(agent_id, [])
            return {
                "events": events,
                "total_events": len(events),
                "agent_id": agent_id
            }
        else:
            # Get all events from all agents
            all_events = []
            for aid, events in stored_events.items():
                for event in events:
                    event_copy = event.copy()
                    event_copy["source_agent"] = aid
                    all_events.append(event_copy)

            # Sort by start time
            all_events.sort(key=lambda x: x.get("start_time", ""))

            return {
                "events": all_events,
                "total_events": len(all_events),
                "agents": list(stored_events.keys())
            }

    except Exception as e:
        logger.error(f"Error retrieving events: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve events: {str(e)}"
        )


@router.get("/events/fullcalendar")
async def get_events_fullcalendar_format():
    """Get events in FullCalendar format for the frontend"""
    try:
        all_events = []

        for agent_id, events in stored_events.items():
            agent_info = agent_status.get(agent_id, {})
            agent_name = agent_info.get("name", f"Agent {agent_id}")

            for event in events:
                # Convert to FullCalendar format
                fc_event = {
                    "id": event.get("id"),
                    "title": event.get("title", "Untitled Event"),
                    "start": event.get("start_time"),
                    "end": event.get("end_time"),
                    "allDay": event.get("all_day", False),
                    "backgroundColor": get_agent_color(agent_id),
                    "borderColor": get_agent_color(agent_id),
                    "extendedProps": {
                        "description": event.get("description", ""),
                        "location": event.get("location", ""),
                        "provider": event.get("provider", "unknown"),
                        "calendar_name": event.get("calendar_name", ""),
                        "agent_name": agent_name,
                        "agent_id": agent_id,
                        "status": event.get("status", "confirmed"),
                        "organizer": event.get("organizer", {}),
                        "participants": event.get("participants", [])
                    }
                }
                all_events.append(fc_event)

        return all_events

    except Exception as e:
        logger.error(f"Error formatting events for FullCalendar: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to format events: {str(e)}"
        )


def get_agent_color(agent_id: str) -> str:
    """Get a consistent color for an agent"""
    colors = [
        "#3788d8",  # Blue
        "#e74c3c",  # Red
        "#2ecc71",  # Green
        "#f39c12",  # Orange
        "#9b59b6",  # Purple
        "#1abc9c",  # Teal
        "#e67e22",  # Carrot
        "#34495e"   # Dark Blue Grey
    ]

    # Use hash of agent_id to consistently assign colors
    hash_val = hash(agent_id) % len(colors)
    return colors[hash_val]


@router.delete("/events/{agent_id}")
async def clear_agent_events(agent_id: str):
    """Clear all events for a specific agent"""
    try:
        if agent_id in stored_events:
            event_count = len(stored_events[agent_id])
            del stored_events[agent_id]

            # Update agent status
            if agent_id in agent_status:
                agent_status[agent_id]["event_count"] = 0

            return {
                "status": "success",
                "message": f"Cleared {event_count} events for agent {agent_id}"
            }
        else:
            return {
                "status": "success",
                "message": f"No events found for agent {agent_id}"
            }

    except Exception as e:
        logger.error(f"Error clearing events for agent {agent_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear events: {str(e)}"
        )


@router.get("/stats")
async def get_sync_stats():
    """Get synchronization statistics"""
    try:
        total_events = sum(len(events) for events in stored_events.values())
        active_agents = len(
            [a for a in agent_status.values() if a.get("status") == "active"])

        # Calculate events by provider
        provider_stats = {}
        for events in stored_events.values():
            for event in events:
                provider = event.get("provider", "unknown")
                provider_stats[provider] = provider_stats.get(provider, 0) + 1

        return {
            "total_events": total_events,
            "total_agents": len(agent_status),
            "active_agents": active_agents,
            "events_by_agent": {aid: len(events) for aid, events in stored_events.items()},
            "events_by_provider": provider_stats,
            "last_updated": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting sync stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get stats: {str(e)}"
        )

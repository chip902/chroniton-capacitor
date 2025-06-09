"""
Synchronization API Router

This module defines the API endpoints for calendar synchronization.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Body, Query
from typing import List, Dict, Any, Optional, Union
import uuid
from datetime import datetime, timedelta

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


@router.post("/config/destination/google")
async def configure_google_destination(
    data: Dict[str, Any] = Body(...),
    controller: CalendarSyncController = Depends(get_sync_controller)
):
    """Configure Google Calendar as the destination with simplified setup"""
    try:
        # Extract required parameters
        calendar_id = data.get("calendar_id", "primary")  # Default to primary calendar
        credentials = data.get("credentials")
        
        if not credentials:
            raise ValueError("Google Calendar credentials are required")
        
        # Create the Google destination configuration
        destination = SyncDestination(
            id="google_destination",
            name="Google Calendar Destination",
            provider_type="google",
            connection_info={
                "api_base_url": "https://www.googleapis.com/calendar/v3",
                "scopes": [
                    "https://www.googleapis.com/auth/calendar",
                    "https://www.googleapis.com/auth/calendar.events"
                ]
            },
            credentials=credentials,
            calendar_id=calendar_id,
            conflict_resolution=ConflictResolution.LATEST_WINS,
            color_management="separate_calendar"  # Create separate calendars for each source
        )
        
        # Configure the destination
        result = await controller.configure_destination(destination)
        
        return {
            "status": "success",
            "message": "Google Calendar destination configured successfully",
            "destination": result.dict(),
            "calendar_id": calendar_id
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to configure Google destination: {str(e)}"
        )


@router.get("/config/google/auth-url")
async def get_google_auth_url():
    """Get Google OAuth2 authorization URL for setting up calendar access"""
    try:
        from auth.google_auth import GoogleCalendarAuth
        
        auth_service = GoogleCalendarAuth()
        auth_url = auth_service.get_authorization_url()
        
        return {
            "auth_url": auth_url,
            "instructions": "Visit this URL to authorize calendar access, then return with the authorization code"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate auth URL: {str(e)}"
        )


@router.post("/config/google/exchange-code")
async def exchange_google_auth_code(
    data: Dict[str, Any] = Body(...)
):
    """Exchange Google authorization code for access tokens"""
    try:
        from auth.google_auth import GoogleCalendarAuth
        
        auth_code = data.get("code")
        if not auth_code:
            raise ValueError("Authorization code is required")
            
        auth_service = GoogleCalendarAuth()
        credentials = await auth_service.exchange_code_for_tokens(auth_code)
        
        return {
            "status": "success",
            "message": "Authorization successful",
            "credentials": credentials,
            "next_step": "Use these credentials to configure Google Calendar destination"
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to exchange authorization code: {str(e)}"
        )


@router.post("/config/google/calendars")
async def list_google_calendars(
    token_info: Dict[str, Any] = Body(...)
):
    """List available Google calendars for the authenticated user"""
    try:
        from services.google_calendar import GoogleCalendarService
        
        google_service = GoogleCalendarService()
        calendars = await google_service.list_calendars(token_info)
        
        return {
            "calendars": calendars,
            "total_count": len(calendars)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to list calendars: {str(e)}"
        )


# CalDAV (Mailcow) Configuration Endpoints

@router.post("/config/caldav/test-connection")
async def test_caldav_connection(
    connection_info: Dict[str, Any] = Body(...)
):
    """Test CalDAV connection to Mailcow server"""
    try:
        from services.caldav_client import CalDAVClient
        
        server_url = connection_info.get('server_url')
        username = connection_info.get('username') 
        password = connection_info.get('password')
        
        if not all([server_url, username, password]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required fields: server_url, username, password"
            )
        
        caldav_client = CalDAVClient(server_url, username, password)
        is_connected = caldav_client.test_connection()
        
        if is_connected:
            return {
                "status": "success",
                "message": "CalDAV connection successful"
            }
        else:
            return {
                "status": "error", 
                "message": "CalDAV connection failed"
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CalDAV connection test failed: {str(e)}"
        )


@router.post("/config/caldav/calendars")
async def list_caldav_calendars(
    connection_info: Dict[str, Any] = Body(...)
):
    """List available CalDAV calendars for the authenticated user"""
    try:
        from services.caldav_client import CalDAVClient
        
        server_url = connection_info.get('server_url')
        username = connection_info.get('username')
        password = connection_info.get('password')
        
        if not all([server_url, username, password]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required fields: server_url, username, password"
            )
        
        caldav_client = CalDAVClient(server_url, username, password)
        calendars = caldav_client.discover_calendars()
        
        return {
            "calendars": calendars,
            "total_count": len(calendars)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to list CalDAV calendars: {str(e)}"
        )


@router.post("/config/destination/caldav")
async def configure_caldav_destination(
    destination_config: Dict[str, Any] = Body(...),
    controller: CalendarSyncController = Depends(get_sync_controller)
):
    """Configure CalDAV (Mailcow) as the destination calendar"""
    try:
        server_url = destination_config.get('server_url')
        username = destination_config.get('username')
        password = destination_config.get('password')
        calendar_url = destination_config.get('calendar_url')
        calendar_name = destination_config.get('calendar_name', 'Mailcow Calendar')
        
        if not all([server_url, username, password, calendar_url]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required fields: server_url, username, password, calendar_url"
            )
        
        # Test the connection first
        from services.caldav_client import CalDAVClient
        caldav_client = CalDAVClient(server_url, username, password)
        
        if not caldav_client.test_connection():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CalDAV connection test failed"
            )
        
        # Create destination configuration
        try:
            destination = SyncDestination(
                id=str(uuid.uuid4()),
                name=calendar_name,
                provider_type="caldav",
                calendar_id=calendar_url,
                connection_info={
                    "server_url": server_url,
                    "username": username,
                    "password": password,
                    "calendar_url": calendar_url
                },
                conflict_resolution=ConflictResolution.DESTINATION_WINS,
                categories={}
            )
            logger.info(f"Created CalDAV destination configuration: {destination.name}")
        except Exception as e:
            logger.error(f"Error creating CalDAV destination: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create destination configuration: {str(e)}"
            )
        
        # Save configuration
        try:
            config = await controller.load_configuration()
            config.destination = destination
            await controller.save_configuration(config)
            logger.info(f"Saved CalDAV destination configuration")
        except Exception as e:
            logger.error(f"Error saving CalDAV configuration: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save configuration: {str(e)}"
            )
        
        return {
            "status": "success",
            "message": "CalDAV destination configured successfully",
            "destination": {
                "provider_type": "caldav",
                "name": calendar_name,
                "calendar_id": calendar_url,
                "server_url": server_url
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to configure CalDAV destination: {str(e)}"
        )


@router.post("/test/end-to-end")
async def test_end_to_end_sync(
    controller: CalendarSyncController = Depends(get_sync_controller)
):
    """Test the complete sync flow from agent events to destination calendar"""
    try:
        # Check if we have stored events from agents
        if not stored_events:
            return {
                "status": "no_data",
                "message": "No agent events available for testing. Agent needs to send heartbeat with events first.",
                "agent_count": len(agent_status),
                "stored_events_count": 0
            }
        
        # Check if destination is configured
        config = await controller.load_configuration()
        if not config.destination:
            return {
                "status": "no_destination",
                "message": "No destination calendar configured. Configure Google Calendar destination first.",
                "stored_events_count": sum(len(events) for events in stored_events.values())
            }
        
        # Run the sync
        result = await controller.sync_agent_events()
        
        return {
            "status": "success",
            "message": "End-to-end sync test completed",
            "sync_result": result,
            "destination": {
                "provider": config.destination.provider_type,
                "calendar_id": config.destination.calendar_id
            }
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"End-to-end sync test failed: {str(e)}",
            "stored_events_count": sum(len(events) for events in stored_events.values())
        }

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
    include_inactive: bool = Query(
        False, description="Include inactive agents"),
    max_inactive_days: int = Query(
        30, description="Max days of inactivity to be considered active"),
    controller: CalendarSyncController = Depends(get_sync_controller)
):
    """List all synchronization agents

    Args:
        include_inactive: If True, include agents that haven't been seen recently
        max_inactive_days: Number of days after which an agent is considered inactive
    """
    try:
        config = await controller.load_configuration()
        agents = getattr(config, 'agents', []) or []

        if not include_inactive:
            # Filter out agents that haven't been seen in max_inactive_days
            cutoff = datetime.utcnow() - timedelta(days=max_inactive_days)
            agents = [
                agent for agent in agents
                if agent.last_seen and agent.last_seen >= cutoff
            ]

        return [agent.dict() for agent in agents]
    except Exception as e:
        logger.error(f"Failed to list agents: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list agents: {str(e)}"
        )


@router.delete("/agents/{agent_id}")
async def delete_agent(
    agent_id: str,
    force: bool = Query(
        False, description="Force delete even if agent is active"),
    controller: CalendarSyncController = Depends(get_sync_controller)
):
    """Delete an agent by ID"""
    try:
        config = await controller.load_configuration()
        agents = getattr(config, 'agents', []) or []

        # Find the agent
        agent = next((a for a in agents if a.id == agent_id), None)
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_id} not found"
            )

        # Check if agent is active (seen in last hour)
        is_active = agent.last_seen and (
            datetime.utcnow() - agent.last_seen) < timedelta(hours=1)
        if is_active and not force:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Agent is currently active. Use force=true to delete an active agent."
            )

        # Remove the agent
        config.agents = [a for a in agents if a.id != agent_id]
        await controller.save_configuration(config)

        return {"status": "success", "message": f"Agent {agent_id} deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete agent {agent_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete agent: {str(e)}"
        )


@router.post("/agents/cleanup")
async def cleanup_inactive_agents(
    max_inactive_days: int = Query(
        30, description="Delete agents inactive for this many days"),
    dry_run: bool = Query(
        True, description="If True, only show what would be deleted"),
    controller: CalendarSyncController = Depends(get_sync_controller)
):
    """Clean up inactive agents

    Args:
        max_inactive_days: Delete agents that haven't been seen in this many days
        dry_run: If True, only return the list of agents that would be deleted
    """
    try:
        config = await controller.load_configuration()
        agents = getattr(config, 'agents', []) or []

        if not agents:
            return {"status": "success", "message": "No agents to clean up", "deleted": []}

        # Find inactive agents
        cutoff = datetime.utcnow() - timedelta(days=max_inactive_days)
        inactive_agents = [
            agent for agent in agents
            if agent.last_seen is None or agent.last_seen < cutoff
        ]

        if dry_run:
            return {
                "status": "dry_run",
                "message": f"Would delete {len(inactive_agents)} inactive agents",
                "agents": [agent.dict() for agent in inactive_agents]
            }

        # Actually delete the agents
        active_agents = [a for a in agents if a not in inactive_agents]
        config.agents = active_agents
        await controller.save_configuration(config)

        return {
            "status": "success",
            "message": f"Deleted {len(inactive_agents)} inactive agents",
            "deleted": [agent.dict() for agent in inactive_agents]
        }

    except Exception as e:
        logger.error(f"Failed to clean up agents: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clean up agents: {str(e)}"
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


@router.get("/agents/{agent_id}/status")
async def get_agent_status(
    agent_id: str,
    controller: CalendarSyncController = Depends(get_sync_controller)
):
    """Get status of a specific agent"""
    try:
        config = await controller.load_configuration()
        agents = getattr(config, 'agents', []) or []
        
        # Find the agent
        agent = next((a for a in agents if a.id == agent_id), None)
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_id} not found"
            )
        
        return agent.dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get agent status: {str(e)}"
        )


@router.post("/agents/register")
async def register_agent(
    agent_data: Dict[str, Any] = Body(...),
    controller: CalendarSyncController = Depends(get_sync_controller)
):
    """Register a new agent with the sync server"""
    try:
        # Store agent registration info
        agent_id = agent_data.get("id")
        if not agent_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Agent ID is required"
            )
        
        # Update agent_status dictionary for tracking
        agent_status[agent_id] = {
            "id": agent_id,
            "name": agent_data.get("name", f"Agent {agent_id}"),
            "environment": agent_data.get("environment", "Unknown"),
            "agent_type": agent_data.get("agent_type", "python"),
            "interval_minutes": agent_data.get("interval_minutes", 60),
            "capabilities": agent_data.get("capabilities", []),
            "config": agent_data.get("config", {}),
            "status": "active",
            "last_seen": datetime.utcnow(),
            "event_count": 0
        }
        
        return {
            "status": "success",
            "message": f"Agent {agent_id} registered successfully",
            "id": agent_id
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register agent: {str(e)}"
        )


@router.post("/agents/{agent_id}/heartbeat")
async def agent_heartbeat(
    agent_id: str,
    data: Dict[str, Any] = Body(...),
    controller: CalendarSyncController = Depends(get_sync_controller)
):
    """Register a heartbeat from a sync agent"""
    print(f"Heartbeat received from agent {agent_id}: {data}")

    try:
        # Update agent status
        if agent_id not in agent_status:
            # Auto-register agent if not found
            agent_status[agent_id] = {
                "id": agent_id,
                "name": f"Agent {agent_id}",
                "environment": data.get("environment", "Unknown"),
                "status": "active",
                "last_seen": datetime.utcnow(),
                "event_count": 0
            }
        else:
            agent_status[agent_id]["last_seen"] = datetime.utcnow()
            agent_status[agent_id]["status"] = data.get("status", "active")
        
        # Process events if included
        events = data.get("events", [])
        if events:
            stored_events[agent_id] = events
            agent_status[agent_id]["event_count"] = len(events)
            print(f"Stored {len(events)} events from agent {agent_id}")
        
        return {
            "status": "success",
            "message": "Heartbeat registered",
            "pending_updates": []  # Could add pending updates here
        }
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
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark update as processed: {str(e)}"
        )


# In-memory storage for demonstration (replace with proper database)
stored_events = {}
agent_status = {}

# Health check endpoint


@router.get("/health")
async def sync_health_check():
    """Check sync service health"""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat()
    }


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

import os
import logging
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from agents.mcp.server import MCPServerStdio

from utils.config import settings
from services.unified_calendar import UnifiedCalendarService
from services.calendar_event import CalendarProvider
from auth.google_auth import GoogleCalendarAuth
from auth.microsoft_auth import MicrosoftGraphAuth

# Set up logging
logger = logging.getLogger(__name__)

async def setup_calendar_mcp_server():
    """
    Set up and return the Calendar MCP server
    """
    # Initialize services
    calendar_service = UnifiedCalendarService()
    google_auth = GoogleCalendarAuth()
    ms_auth = MicrosoftGraphAuth()
    
    # Create the MCP server configuration
    mcp_config = {
        "openapi": {
            "info": {
                "title": "Calendar Integration API",
                "version": "1.0.0",
                "description": "API for integrating with multiple calendar providers"
            },
            "servers": [
                {
                    "url": "http://localhost:8000",
                    "description": "Calendar microservice"
                }
            ],
            "paths": {
                "/auth/google": {
                    "get": {
                        "operationId": "getGoogleAuthUrl",
                        "summary": "Get Google OAuth authorization URL",
                        "parameters": [
                            {
                                "name": "tenant_id",
                                "in": "query",
                                "required": False,
                                "schema": {"type": "string"}
                            }
                        ],
                        "responses": {
                            "200": {
                                "description": "Authentication URL",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "auth_url": {"type": "string"}
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                },
                "/auth/microsoft": {
                    "get": {
                        "operationId": "getMicrosoftAuthUrl",
                        "summary": "Get Microsoft OAuth authorization URL",
                        "parameters": [
                            {
                                "name": "tenant_id",
                                "in": "query",
                                "required": False,
                                "schema": {"type": "string"}
                            }
                        ],
                        "responses": {
                            "200": {
                                "description": "Authentication URL",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "auth_url": {"type": "string"}
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                },
                "/calendars": {
                    "get": {
                        "operationId": "listCalendars",
                        "summary": "List calendars from all providers",
                        "parameters": [
                            {
                                "name": "credentials",
                                "in": "query",
                                "description": "JSON string of provider credentials",
                                "required": True,
                                "schema": {"type": "string"}
                            }
                        ],
                        "responses": {
                            "200": {
                                "description": "Calendars by provider",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "additionalProperties": {
                                                "type": "array",
                                                "items": {
                                                    "type": "object"
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                },
                "/events": {
                    "get": {
                        "operationId": "getEvents",
                        "summary": "Get events from multiple calendars",
                        "parameters": [
                            {
                                "name": "credentials",
                                "in": "query",
                                "description": "JSON string of provider credentials",
                                "required": True,
                                "schema": {"type": "string"}
                            },
                            {
                                "name": "calendars",
                                "in": "query",
                                "description": "JSON string of calendar selections",
                                "required": True,
                                "schema": {"type": "string"}
                            },
                            {
                                "name": "start",
                                "in": "query",
                                "description": "Start date in ISO format",
                                "required": False,
                                "schema": {"type": "string", "format": "date-time"}
                            },
                            {
                                "name": "end",
                                "in": "query",
                                "description": "End date in ISO format",
                                "required": False,
                                "schema": {"type": "string", "format": "date-time"}
                            },
                            {
                                "name": "sync_tokens",
                                "in": "query",
                                "description": "JSON string of sync tokens",
                                "required": False,
                                "schema": {"type": "string"}
                            }
                        ],
                        "responses": {
                            "200": {
                                "description": "Events and sync tokens",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "events": {
                                                    "type": "array",
                                                    "items": {"type": "object"}
                                                },
                                                "syncTokens": {"type": "object"}
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    
    # Create handlers for MCP server
    async def handle_get_google_auth_url(tenant_id: Optional[str] = None):
        """Handler for getGoogleAuthUrl operation"""
        return google_auth.create_auth_url(tenant_id)
    
    async def handle_get_microsoft_auth_url(tenant_id: Optional[str] = None):
        """Handler for getMicrosoftAuthUrl operation"""
        return ms_auth.create_auth_url(tenant_id)
    
    async def handle_list_calendars(credentials: str):
        """Handler for listCalendars operation"""
        user_credentials = json.loads(credentials)
        return await calendar_service.list_all_calendars(user_credentials)
    
    async def handle_get_events(
        credentials: str,
        calendars: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
        sync_tokens: Optional[str] = None
    ):
        """Handler for getEvents operation"""
        # Parse parameters
        user_credentials = json.loads(credentials)
        calendar_selections = json.loads(calendars)
        
        # Parse dates if provided
        start_date = datetime.fromisoformat(start) if start else None
        end_date = datetime.fromisoformat(end) if end else None
        
        # Parse sync tokens if provided
        tokens = json.loads(sync_tokens) if sync_tokens else None
        
        # Get events
        result = await calendar_service.get_all_events(
            user_credentials=user_credentials,
            calendar_selections=calendar_selections,
            start_date=start_date,
            end_date=end_date,
            sync_tokens=tokens
        )
        
        # Convert events to dictionaries
        events_dict = [event.dict() for event in result["events"]]
        
        return {
            "events": events_dict,
            "syncTokens": result["syncTokens"]
        }
    
    # Create handlers mapping
    handlers = {
        "getGoogleAuthUrl": handle_get_google_auth_url,
        "getMicrosoftAuthUrl": handle_get_microsoft_auth_url,
        "listCalendars": handle_list_calendars,
        "getEvents": handle_get_events
    }
    
    # Create the MCP server
    calendar_mcp_server = MCPServerStdio(
        name=settings.MCP_SERVICE_NAME,
        openapi_schema=mcp_config["openapi"],
        operation_handlers=handlers
    )
    
    # Initialize the server
    await calendar_mcp_server.initialize()
    logger.info(f"Calendar MCP server initialized with {len(handlers)} handlers")
    
    return calendar_mcp_server
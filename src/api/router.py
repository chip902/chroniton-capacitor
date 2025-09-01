from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import json

from services.unified_calendar import UnifiedCalendarService
from services.calendar_event import CalendarProvider
from auth.google_auth import GoogleCalendarAuth
from auth.microsoft_auth import MicrosoftGraphAuth
from auth.exchange_auth import ExchangeAuth
from utils.config import settings

# Import routers
from api.exchange_router import router as exchange_router
from api.oauth_router import router as oauth_router

# Initialize API router
router = APIRouter()

# Include routers
router.include_router(exchange_router)
router.include_router(oauth_router)

# Initialize services
google_auth = GoogleCalendarAuth()
ms_auth = MicrosoftGraphAuth()
exchange_auth = ExchangeAuth()
calendar_service = UnifiedCalendarService()

# Simple route for testing


@router.get("/ping")
async def ping():
    """Simple health check endpoint"""
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}

# Authentication routes


@router.get("/auth/google")
async def google_auth_url(
    tenant_id: Optional[str] = None,
    redirect_uri: Optional[str] = None
):
    """Get Google OAuth URL for authentication"""
    return google_auth.create_auth_url(tenant_id, redirect_uri)


# NOTE: Google OAuth callback moved to oauth_router.py
# This old callback was conflicting with the new one that supports redirects


@router.get("/auth/microsoft")
async def microsoft_auth_url(tenant_id: Optional[str] = None):
    """Get Microsoft OAuth URL for authentication"""
    return ms_auth.create_auth_url(tenant_id)


@router.get("/auth/microsoft/callback")
async def microsoft_auth_callback(code: str, state: Optional[str] = None):
    """Handle Microsoft OAuth callback and exchange code for tokens"""
    token_info = await ms_auth.exchange_code(code, tenant_id=state)
    return token_info

# Calendar routes


@router.get("/calendars")
async def list_calendars(credentials: str = Query(..., description="JSON string of provider credentials")):
    """List calendars from all providers the user is authenticated with"""
    try:
        # Parse credentials
        user_credentials = json.loads(credentials)

        calendars = await calendar_service.list_all_calendars(user_credentials)
        return calendars
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to list calendars: {str(e)}"
        )


@router.get("/events")
async def get_events(
    credentials: str = Query(...,
                             description="JSON string of provider credentials"),
    calendars: str = Query(...,
                           description="JSON string of calendar selections"),
    start: Optional[str] = Query(None, description="Start date in ISO format"),
    end: Optional[str] = Query(None, description="End date in ISO format"),
    sync_tokens: Optional[str] = Query(
        None, description="JSON string of sync tokens")
):
    """Get events from multiple calendars across providers"""
    try:
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
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to get events: {str(e)}"
        )

# Calendar metadata management endpoints


@router.put("/calendars/{calendar_id}")
async def update_calendar_metadata(
    calendar_id: str,
    updates: Dict[str, Any],
    provider: str = Query(...,
                          description="Calendar provider (google, microsoft, exchange)"),
    credentials: str = Query(...,
                             description="JSON string of provider credentials")
):
    """Update calendar metadata like name, color, description"""
    try:
        # Parse credentials
        user_credentials = json.loads(credentials)

        # Update calendar metadata
        result = await calendar_service.update_calendar_metadata(
            provider=provider,
            calendar_id=calendar_id,
            credentials=user_credentials,
            updates=updates
        )

        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update calendar metadata: {str(e)}"
        )


@router.post("/calendars")
async def create_calendar(
    calendar_data: Dict[str, Any],
    provider: str = Query(...,
                          description="Calendar provider (google, microsoft, exchange)"),
    credentials: str = Query(...,
                             description="JSON string of provider credentials")
):
    """Create a new calendar"""
    try:
        # Parse credentials
        user_credentials = json.loads(credentials)

        # Create calendar
        result = await calendar_service.create_calendar(
            provider=provider,
            credentials=user_credentials,
            calendar_data=calendar_data
        )

        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create calendar: {str(e)}"
        )


@router.delete("/calendars/{calendar_id}")
async def delete_calendar(
    calendar_id: str,
    provider: str = Query(...,
                          description="Calendar provider (google, microsoft, exchange)"),
    credentials: str = Query(...,
                             description="JSON string of provider credentials")
):
    """Delete a calendar"""
    try:
        # Parse credentials
        user_credentials = json.loads(credentials)

        # Delete calendar
        result = await calendar_service.delete_calendar(
            provider=provider,
            calendar_id=calendar_id,
            credentials=user_credentials
        )

        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to delete calendar: {str(e)}"
        )

# Enhanced Calendar Service Endpoints

@router.get("/apple/calendars")
async def list_apple_calendars():
    """List Apple Calendar calendars using enhanced access method"""
    try:
        from services.apple_calendar_enhanced import AppleCalendarService
        apple_service = AppleCalendarService()
        
        if not apple_service.is_available():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Apple Calendar access not available on this system"
            )
        
        calendars = await apple_service.list_calendars()
        return {
            "calendars": calendars,
            "access_method": apple_service.get_access_method(),
            "available": apple_service.is_available()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to list Apple calendars: {str(e)}"
        )

@router.get("/apple/events/{calendar_id}")
async def get_apple_events(
    calendar_id: str,
    start: Optional[str] = Query(None, description="Start date in ISO format"),
    end: Optional[str] = Query(None, description="End date in ISO format"),
    max_results: int = Query(100, description="Maximum number of events")
):
    """Get events from an Apple Calendar using enhanced access method"""
    try:
        from services.apple_calendar_enhanced import AppleCalendarService
        apple_service = AppleCalendarService()
        
        if not apple_service.is_available():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Apple Calendar access not available on this system"
            )
        
        # Parse dates if provided
        start_date = datetime.fromisoformat(start) if start else None
        end_date = datetime.fromisoformat(end) if end else None
        
        events = await apple_service.get_events(
            calendar_id=calendar_id,
            start_date=start_date,
            end_date=end_date,
            max_results=max_results
        )
        
        # Convert events to dictionaries
        events_dict = [event.dict() for event in events] if events else []
        
        return {
            "events": events_dict,
            "calendar_id": calendar_id,
            "access_method": apple_service.get_access_method(),
            "count": len(events_dict)
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to get Apple Calendar events: {str(e)}"
        )

@router.post("/exchange/calendars")
async def list_exchange_calendars(exchange_config: dict):
    """List Exchange calendars using enhanced EWS access method"""
    try:
        from services.exchange_calendar_enhanced import ExchangeCalendarService, ExchangeConfig
        
        # Create config from request
        config = ExchangeConfig(
            server_url=exchange_config.get('server_url', ''),
            username=exchange_config.get('username', ''),
            password=exchange_config.get('password', ''),
            email=exchange_config.get('email', ''),
            auth_type=exchange_config.get('auth_type', 'basic'),
            verify_ssl=exchange_config.get('verify_ssl', True)
        )
        
        exchange_service = ExchangeCalendarService(config)
        
        # Test connection first
        if not exchange_service.test_connection():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to connect to Exchange server. Check credentials."
            )
        
        calendars = await exchange_service.list_calendars()
        server_info = exchange_service.get_server_info()
        
        return {
            "calendars": calendars,
            "server_info": server_info,
            "available": ExchangeCalendarService.is_available()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to list Exchange calendars: {str(e)}"
        )

@router.post("/exchange/events/{calendar_id}")
async def get_exchange_events(
    calendar_id: str,
    exchange_config: dict,
    start: Optional[str] = Query(None, description="Start date in ISO format"),
    end: Optional[str] = Query(None, description="End date in ISO format"),
    max_results: int = Query(100, description="Maximum number of events")
):
    """Get events from an Exchange calendar using enhanced EWS access method"""
    try:
        from services.exchange_calendar_enhanced import ExchangeCalendarService, ExchangeConfig
        
        # Create config from request
        config = ExchangeConfig(
            server_url=exchange_config.get('server_url', ''),
            username=exchange_config.get('username', ''),
            password=exchange_config.get('password', ''),
            email=exchange_config.get('email', ''),
            auth_type=exchange_config.get('auth_type', 'basic'),
            verify_ssl=exchange_config.get('verify_ssl', True)
        )
        
        exchange_service = ExchangeCalendarService(config)
        
        # Parse dates if provided
        start_date = datetime.fromisoformat(start) if start else None
        end_date = datetime.fromisoformat(end) if end else None
        
        events = await exchange_service.get_events(
            calendar_id=calendar_id,
            start_date=start_date,
            end_date=end_date,
            max_results=max_results
        )
        
        # Convert events to dictionaries
        events_dict = [event.dict() for event in events] if events else []
        
        return {
            "events": events_dict,
            "calendar_id": calendar_id,
            "count": len(events_dict),
            "available": ExchangeCalendarService.is_available()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to get Exchange events: {str(e)}"
        )

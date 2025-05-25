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

# Import the Exchange router
from api.exchange_router import router as exchange_router

# Initialize API router
router = APIRouter()

# Include the Exchange router
router.include_router(exchange_router)

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
async def google_auth_url(tenant_id: Optional[str] = None):
    """Get Google OAuth URL for authentication"""
    return google_auth.create_auth_url(tenant_id)

@router.get("/auth/google/callback")
async def google_auth_callback(code: str):
    """Handle Google OAuth callback and exchange code for tokens"""
    token_info = await google_auth.exchange_code(code)
    return token_info

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
    credentials: str = Query(..., description="JSON string of provider credentials"),
    calendars: str = Query(..., description="JSON string of calendar selections"),
    start: Optional[str] = Query(None, description="Start date in ISO format"),
    end: Optional[str] = Query(None, description="End date in ISO format"),
    sync_tokens: Optional[str] = Query(None, description="JSON string of sync tokens")
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
    provider: str = Query(..., description="Calendar provider (google, microsoft, exchange)"),
    credentials: str = Query(..., description="JSON string of provider credentials")
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
    provider: str = Query(..., description="Calendar provider (google, microsoft, exchange)"),
    credentials: str = Query(..., description="JSON string of provider credentials")
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
    provider: str = Query(..., description="Calendar provider (google, microsoft, exchange)"),
    credentials: str = Query(..., description="JSON string of provider credentials")
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
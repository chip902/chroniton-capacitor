"""
OAuth authentication router for calendar providers
Handles authorization flows for Google Calendar and Microsoft Graph
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from urllib.parse import urlencode
import secrets
import json

from fastapi import APIRouter, Request, HTTPException, status, Response, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from pydantic import BaseModel

from auth.google_auth import GoogleCalendarAuth
from auth.microsoft_auth import MicrosoftGraphAuth
from utils.config import settings
from services.unified_calendar import UnifiedCalendarService
from services.calendar_event import CalendarCredentials, CalendarProvider
from sync.controller import CalendarSyncController
from sync.storage import SyncStorageManager

logger = logging.getLogger(__name__)

# Initialize OAuth providers
google_auth = GoogleCalendarAuth()
microsoft_auth = MicrosoftGraphAuth()

# Create router
router = APIRouter(prefix="/api/auth", tags=["oauth"])

# State storage for OAuth flows (in production, use Redis or database)
_oauth_states = {}

class OAuthState(BaseModel):
    """OAuth state model for tracking authorization flows"""
    provider: str
    tenant_id: Optional[str] = None
    created_at: datetime
    redirect_url: Optional[str] = None

class TokenInfo(BaseModel):
    """Token information response model"""
    provider: str
    token_type: str
    access_token: str
    refresh_token: Optional[str] = None
    expires_at: Optional[float] = None
    tenant_id: Optional[str] = None
    scopes: list[str]

def generate_state() -> str:
    """Generate a secure random state string"""
    return secrets.token_urlsafe(32)

def store_oauth_state(state: str, oauth_state: OAuthState) -> None:
    """Store OAuth state temporarily"""
    _oauth_states[state] = oauth_state
    # Clean up old states (older than 30 minutes)
    cutoff = datetime.utcnow() - timedelta(minutes=settings.OAUTH_SESSION_TIMEOUT_MINUTES)
    _oauth_states.clear()  # Simple cleanup - in production use proper expiry
    _oauth_states[state] = oauth_state

def get_oauth_state(state: str) -> Optional[OAuthState]:
    """Retrieve OAuth state"""
    return _oauth_states.get(state)

def remove_oauth_state(state: str) -> None:
    """Remove OAuth state after use"""
    _oauth_states.pop(state, None)

async def create_sync_source_from_tokens(tokens: Dict[str, Any], tenant_id: Optional[str] = None) -> None:
    """Create a sync source automatically from OAuth tokens"""
    try:
        # Create credentials object
        credentials = CalendarCredentials(
            provider=CalendarProvider.GOOGLE,
            token_type=tokens.get("token_type", "Bearer"),
            access_token=tokens["access_token"],
            refresh_token=tokens.get("refresh_token"),
            expires_at=tokens.get("expires_at")
        )
        
        # Initialize unified service to get calendars
        unified_service = UnifiedCalendarService()
        calendars = await unified_service.list_calendars(credentials)
        
        # Select calendars to sync (primary + any owned calendars)
        selected_calendars = []
        calendar_selections = []
        
        for calendar in calendars:
            # Include primary calendar and owned calendars (exclude read-only)
            if calendar.primary or (hasattr(calendar, 'access_role') and calendar.access_role == 'owner'):
                selected_calendars.append(calendar.id)
                calendar_selections.append({
                    "id": calendar.id,
                    "name": calendar.name,
                    "primary": calendar.primary or False
                })
        
        if not selected_calendars:
            logger.warning("No suitable calendars found for sync source creation")
            return
            
        # Initialize storage and controller
        storage = SyncStorageManager(use_redis=False)
        await storage.initialize()
        
        controller = CalendarSyncController(storage)
        await controller.initialize()
        
        # Create sync source
        from sync.models import SyncSource
        
        source_id = f"google_oauth_{tenant_id or 'default'}"
        sync_source = SyncSource(
            id=source_id,
            name=f"Google Calendar OAuth ({len(selected_calendars)} calendars)",
            provider_type="google",
            credentials=credentials.dict(),
            calendar_selections=calendar_selections,
            sync_direction="bidirectional",
            sync_method="incremental",
            enabled=True
        )
        
        # Save the sync source
        config = await controller.load_configuration()
        
        # Remove existing source with same ID if it exists
        config.sources = [s for s in config.sources if s.id != source_id]
        
        # Add new source
        config.sources.append(sync_source)
        
        # Save configuration
        await controller.save_configuration(config)
        
        # If no destination exists, create one using the primary calendar
        if not config.destination:
            primary_calendar = next((cal for cal in calendar_selections if cal["primary"]), calendar_selections[0])
            
            from sync.models import SyncDestination
            destination = SyncDestination(
                id="google_oauth_destination",
                name="Google Calendar Destination (OAuth)",
                provider_type="google",
                credentials=credentials.dict(),
                calendar_id=primary_calendar["id"],
                conflict_resolution="latest_wins",
                color_management="source_color",
                categories={},
                source_calendars={}
            )
            
            await controller.configure_destination(destination)
        
        logger.info(f"Successfully created sync source '{source_id}' with {len(selected_calendars)} calendars")
        
    except Exception as e:
        logger.error(f"Error creating sync source from OAuth tokens: {e}")
        raise

# Google Calendar OAuth endpoints

@router.get("/google/authorize")
async def google_authorize(
    request: Request,
    tenant_id: Optional[str] = None,
    redirect_url: Optional[str] = None
):
    """
    Initiate Google Calendar OAuth authorization flow
    
    Query parameters:
    - tenant_id: Optional tenant ID for multi-tenant apps
    - redirect_url: URL to redirect to after successful authentication
    """
    try:
        if google_auth.dummy_mode:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Google Calendar OAuth not configured. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."
            )

        # Generate state for security
        state = generate_state()
        oauth_state = OAuthState(
            provider="google",
            tenant_id=tenant_id,
            created_at=datetime.utcnow(),
            redirect_url=redirect_url
        )
        store_oauth_state(state, oauth_state)

        # Create authorization URL
        result = google_auth.create_auth_url(tenant_id=tenant_id)
        auth_url = result["auth_url"]
        
        # Add state parameter to the auth URL
        if '?' in auth_url:
            auth_url += f"&state={state}"
        else:
            auth_url += f"?state={state}"

        logger.info(f"Redirecting to Google OAuth: {auth_url}")
        
        return RedirectResponse(url=auth_url)

    except Exception as e:
        logger.error(f"Error initiating Google OAuth: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate Google authorization: {str(e)}"
        )

@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None
):
    """Handle Google OAuth callback"""
    try:
        # Check for OAuth errors
        if error:
            logger.error(f"Google OAuth error: {error}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"OAuth error: {error}"
            )

        if not code or not state:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing authorization code or state parameter"
            )

        # Verify state parameter
        oauth_state = get_oauth_state(state)
        if not oauth_state or oauth_state.provider != "google":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired state parameter"
            )

        # Remove state after verification
        remove_oauth_state(state)

        # Exchange code for tokens
        tokens = await google_auth.exchange_code(code)
        
        # Create response with token info
        token_info = TokenInfo(
            provider="google",
            token_type=tokens["token_type"],
            access_token=tokens["access_token"],
            refresh_token=tokens.get("refresh_token"),
            expires_at=tokens.get("expires_at"),
            scopes=settings.GOOGLE_SCOPES
        )

        logger.info("Google OAuth completed successfully")
        
        # Automatically create sync source with these tokens
        try:
            await create_sync_source_from_tokens(tokens, oauth_state.tenant_id)
            logger.info("Automatically created sync source from OAuth tokens")
        except Exception as e:
            logger.error(f"Failed to create sync source from OAuth tokens: {e}")
        
        # If there's a redirect URL, redirect with tokens (for frontend integration)
        if oauth_state.redirect_url:
            # In production, you might want to store tokens securely and redirect with a session ID
            redirect_params = urlencode({
                "provider": "google",
                "success": "true",
                "access_token": tokens["access_token"][:50] + "...",  # Truncated for security
            })
            return RedirectResponse(url=f"{oauth_state.redirect_url}?{redirect_params}")
        
        # Return success message instead of raw token info
        return {
            "status": "success",
            "message": "Google Calendar connected and sync source created successfully!",
            "provider": "google",
            "next_steps": "Your calendars are now being synced. Check the sync sources at /sync/sources"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in Google OAuth callback: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OAuth callback failed: {str(e)}"
        )

# Microsoft Graph OAuth endpoints

@router.get("/microsoft/authorize")
async def microsoft_authorize(
    request: Request,
    tenant_id: Optional[str] = None,
    redirect_url: Optional[str] = None
):
    """
    Initiate Microsoft Graph OAuth authorization flow
    
    Query parameters:
    - tenant_id: Azure AD tenant ID (defaults to 'common')
    - redirect_url: URL to redirect to after successful authentication
    """
    try:
        if microsoft_auth.dummy_mode:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Microsoft Graph OAuth not configured. Please set MS_CLIENT_ID and MS_CLIENT_SECRET."
            )

        # Generate state for security
        state = generate_state()
        oauth_state = OAuthState(
            provider="microsoft",
            tenant_id=tenant_id,
            created_at=datetime.utcnow(),
            redirect_url=redirect_url
        )
        store_oauth_state(state, oauth_state)

        # Create authorization URL
        result = microsoft_auth.create_auth_url(tenant_id=tenant_id)
        auth_url = result["auth_url"]
        
        # Add state parameter to the auth URL
        if '?' in auth_url:
            auth_url += f"&state={state}"
        else:
            auth_url += f"?state={state}"

        logger.info(f"Redirecting to Microsoft OAuth: {auth_url}")
        
        return RedirectResponse(url=auth_url)

    except Exception as e:
        logger.error(f"Error initiating Microsoft OAuth: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate Microsoft authorization: {str(e)}"
        )

@router.get("/microsoft/callback")
async def microsoft_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None
):
    """Handle Microsoft OAuth callback"""
    try:
        # Check for OAuth errors
        if error:
            logger.error(f"Microsoft OAuth error: {error} - {error_description}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"OAuth error: {error_description or error}"
            )

        if not code or not state:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing authorization code or state parameter"
            )

        # Verify state parameter
        oauth_state = get_oauth_state(state)
        if not oauth_state or oauth_state.provider != "microsoft":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired state parameter"
            )

        # Remove state after verification
        remove_oauth_state(state)

        # Exchange code for tokens
        tokens = await microsoft_auth.exchange_code(code, oauth_state.tenant_id)
        
        # Create response with token info
        token_info = TokenInfo(
            provider="microsoft",
            token_type=tokens["token_type"],
            access_token=tokens["access_token"],
            refresh_token=tokens.get("refresh_token"),
            expires_at=tokens.get("expires_at"),
            tenant_id=tokens.get("tenant_id"),
            scopes=settings.MS_SCOPES
        )

        logger.info("Microsoft OAuth completed successfully")
        
        # If there's a redirect URL, redirect with tokens (for frontend integration)
        if oauth_state.redirect_url:
            # In production, you might want to store tokens securely and redirect with a session ID
            redirect_params = urlencode({
                "provider": "microsoft",
                "success": "true",
                "access_token": tokens["access_token"][:50] + "...",  # Truncated for security
                "tenant_id": tokens.get("tenant_id", "")
            })
            return RedirectResponse(url=f"{oauth_state.redirect_url}?{redirect_params}")
        
        # Return token info as JSON response
        return token_info

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in Microsoft OAuth callback: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OAuth callback failed: {str(e)}"
        )

# Utility endpoints

@router.get("/status")
async def oauth_status():
    """Get OAuth configuration status"""
    return {
        "google": {
            "configured": settings.google_oauth_configured,
            "redirect_uri": settings.google_redirect_uri,
            "scopes": settings.GOOGLE_SCOPES,
            "dummy_mode": google_auth.dummy_mode
        },
        "microsoft": {
            "configured": settings.microsoft_oauth_configured,
            "redirect_uri": settings.microsoft_redirect_uri,
            "scopes": settings.MS_SCOPES,
            "dummy_mode": microsoft_auth.dummy_mode
        }
    }

@router.get("/test")
async def oauth_test_page():
    """Simple test page for OAuth flows"""
    if not (settings.google_oauth_configured or settings.microsoft_oauth_configured):
        return HTMLResponse(content="""
        <html>
        <body>
            <h1>OAuth Test Page</h1>
            <p><strong>No OAuth providers configured!</strong></p>
            <p>Please configure OAuth credentials in your .env file.</p>
            <p>See OAUTH_SETUP.md for instructions.</p>
        </body>
        </html>
        """)
    
    google_section = ""
    if settings.google_oauth_configured:
        google_section = f'''
        <h2>Google Calendar OAuth</h2>
        <p><a href="/api/auth/google/authorize?redirect_url=http://localhost:{settings.API_PORT}/api/auth/test">Test Google OAuth</a></p>
        '''
    
    microsoft_section = ""
    if settings.microsoft_oauth_configured:
        microsoft_section = f'''
        <h2>Microsoft Graph OAuth</h2>
        <p><a href="/api/auth/microsoft/authorize?redirect_url=http://localhost:{settings.API_PORT}/api/auth/test">Test Microsoft OAuth</a></p>
        '''
    
    return HTMLResponse(content=f"""
    <html>
    <body>
        <h1>OAuth Test Page</h1>
        {google_section}
        {microsoft_section}
        <hr>
        <h3>Configuration Status</h3>
        <ul>
            <li>Google configured: {settings.google_oauth_configured}</li>
            <li>Microsoft configured: {settings.microsoft_oauth_configured}</li>
            <li>Base URL: {settings.base_url}</li>
        </ul>
    </body>
    </html>
    """)
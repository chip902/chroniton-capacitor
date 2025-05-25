import os
from typing import Dict, Optional, List
import json
from fastapi import HTTPException, status
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from utils.config import settings

# OAuth scope for Google Calendar API
SCOPES = [
    'https://www.googleapis.com/auth/calendar.readonly',
    'https://www.googleapis.com/auth/calendar.events.readonly'
]

class GoogleCalendarAuth:
    def __init__(self):
        """Initialize Google Calendar authentication"""
        self.client_id = settings.GOOGLE_CLIENT_ID
        self.client_secret = settings.GOOGLE_CLIENT_SECRET
        self.redirect_uri = settings.GOOGLE_REDIRECT_URI
        
        if not all([self.client_id, self.client_secret]):
            raise ValueError("Google Calendar API credentials not configured")
    
    def create_auth_url(self, tenant_id: Optional[str] = None) -> Dict[str, str]:
        """
        Create authentication URL for Google OAuth flow
        Optionally specify a tenant_id for multi-tenant applications
        """
        # Create OAuth flow instance
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [self.redirect_uri]
                }
            },
            scopes=SCOPES
        )
        
        # Set redirect URI
        flow.redirect_uri = self.redirect_uri
        
        # Generate authorization URL
        # If tenant_id is provided, we could store it in the state parameter
        # This example doesn't directly use it for Google auth, but we include it for consistency
        # with the Microsoft authentication method
        state = tenant_id if tenant_id else ""
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent',
            state=state
        )
        
        return {"auth_url": auth_url}
    
    async def exchange_code(self, code: str) -> Dict[str, str]:
        """Exchange authorization code for tokens"""
        try:
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [self.redirect_uri]
                    }
                },
                scopes=SCOPES
            )
            
            flow.redirect_uri = self.redirect_uri
            
            # Exchange authorization code for tokens
            flow.fetch_token(code=code)
            
            # Get credentials
            credentials = flow.credentials
            
            # Return tokens as dict
            return {
                "token_type": "Bearer",
                "access_token": credentials.token,
                "refresh_token": credentials.refresh_token,
                "expires_at": credentials.expiry.timestamp() if credentials.expiry else None
            }
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to exchange code: {str(e)}"
            )
    
    def get_credentials(self, token_info: Dict[str, str]) -> Credentials:
        """Create Google OAuth credentials from token info"""
        return Credentials(
            token=token_info.get("access_token"),
            refresh_token=token_info.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.client_id,
            client_secret=self.client_secret,
            scopes=SCOPES
        )
    
    async def get_calendar_service(self, token_info: Dict[str, str]):
        """Get Google Calendar API service using token info"""
        try:
            credentials = self.get_credentials(token_info)
            service = build('calendar', 'v3', credentials=credentials)
            return service
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Failed to authenticate with Google Calendar: {str(e)}"
            )
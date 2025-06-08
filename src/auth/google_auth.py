import os
from typing import Dict, Optional, List, Any
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

# Dummy calendar service for when credentials aren't available


class DummyCalendarService:
    """A dummy implementation of Google Calendar service for testing"""

    def __init__(self):
        self.dummy = True

    def events(self):
        return DummyEventsResource()

    def calendars(self):
        return DummyCalendarsResource()

    def calendarList(self):
        return DummyCalendarListResource()


class DummyEventsResource:
    def list(self, **kwargs):
        return DummyRequest({"items": []})

    def insert(self, **kwargs):
        return DummyRequest({"id": "dummy-event-id"})

    def update(self, **kwargs):
        return DummyRequest({"id": "dummy-event-id", "updated": True})

    def delete(self, **kwargs):
        return DummyRequest({"deleted": True})


class DummyCalendarsResource:
    def get(self, **kwargs):
        return DummyRequest({"id": "dummy-calendar-id"})


class DummyCalendarListResource:
    def list(self, **kwargs):
        return DummyRequest({"items": []})


class DummyRequest:
    def __init__(self, result):
        self.result_data = result

    def execute(self):
        return self.result_data


class GoogleCalendarAuth:
    def __init__(self):
        """Initialize Google Calendar authentication"""
        self.client_id = settings.GOOGLE_CLIENT_ID
        self.client_secret = settings.GOOGLE_CLIENT_SECRET
        self.redirect_uri = settings.GOOGLE_REDIRECT_URI

        # Instead of raising an error, just set a flag indicating we're in dummy mode
        self.dummy_mode = not all([self.client_id, self.client_secret])
        if self.dummy_mode:
            print("WARNING: Google Calendar API credentials not configured. Running in limited functionality mode.")
        else:
            print("Google Calendar authentication initialized successfully")

    def create_auth_url(self, tenant_id: Optional[str] = None, redirect_uri: Optional[str] = None) -> Dict[str, str]:
        """
        Create authentication URL for Google OAuth flow
        Optionally specify a tenant_id for multi-tenant applications
        Optionally specify a custom redirect_uri for different environments
        """
        if self.dummy_mode:
            return {"auth_url": "https://dummy-auth-url.example.com", "state": "dummy-state"}

        # Use provided redirect_uri or fall back to configured default
        actual_redirect_uri = redirect_uri or self.redirect_uri

        # Create OAuth flow instance
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    # Use dynamic redirect URI
                    "redirect_uris": [actual_redirect_uri]
                }
            },
            scopes=SCOPES
        )

        # Set redirect URI to the actual one we want to use
        flow.redirect_uri = actual_redirect_uri

        # Generate authorization URL
        state = tenant_id if tenant_id else ""
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent',
            state=state
        )

        return {"auth_url": auth_url}

    async def exchange_code(self, code: str, redirect_uri: Optional[str] = None) -> Dict[str, str]:
        """Exchange authorization code for tokens"""
        if self.dummy_mode:
            return {
                "token_type": "Bearer",
                "access_token": "dummy-access-token",
                "refresh_token": "dummy-refresh-token",
                "expires_at": None
            }

        try:
            # Use provided redirect_uri or fall back to configured default
            actual_redirect_uri = redirect_uri or self.redirect_uri

            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        # Use dynamic redirect URI
                        "redirect_uris": [actual_redirect_uri]
                    }
                },
                scopes=SCOPES
            )

            # IMPORTANT: Use the same redirect_uri that was used for auth URL creation
            flow.redirect_uri = actual_redirect_uri

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
        if self.dummy_mode:
            # Create dummy credentials for testing
            return Credentials(
                token="dummy-token",
                refresh_token="dummy-refresh",
                token_uri="https://oauth2.googleapis.com/token",
                client_id="dummy-client-id",
                client_secret="dummy-client-secret",
                scopes=SCOPES
            )

        return Credentials(
            token=token_info.get("access_token"),
            refresh_token=token_info.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.client_id,
            client_secret=self.client_secret,
            scopes=SCOPES
        )

    async def get_calendar_service(self, token_info: Dict[str, str]) -> Any:
        """Get Google Calendar API service using token info"""
        if self.dummy_mode:
            # Return a dummy service for testing
            return DummyCalendarService()

        try:
            credentials = self.get_credentials(token_info)
            service = build('calendar', 'v3', credentials=credentials)
            return service
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Failed to authenticate with Google Calendar: {str(e)}"
            )

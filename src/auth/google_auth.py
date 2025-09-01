import os
from typing import Dict, Optional, List, Any
import json
from fastapi import HTTPException, status
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from utils.config import settings

# OAuth scopes are now defined in settings

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
        self.scopes = settings.GOOGLE_SCOPES
        
        # Use the dynamic redirect URI from settings
        self.redirect_uri = settings.google_redirect_uri

        # Check if OAuth is properly configured
        self.dummy_mode = not settings.google_oauth_configured
        if self.dummy_mode:
            print("WARNING: Google Calendar API credentials not configured. Running in limited functionality mode.")
            print(f"Expected redirect URI: {self.redirect_uri}")
            print("Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in your .env file")
        else:
            print("Google Calendar authentication initialized successfully")
            print(f"Using redirect URI: {self.redirect_uri}")

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
            scopes=self.scopes
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
                scopes=self.scopes
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
                scopes=self.scopes
            )

        return Credentials(
            token=token_info.get("access_token"),
            refresh_token=token_info.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.client_id,
            client_secret=self.client_secret,
            scopes=self.scopes
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

    def get_authorization_url(self, tenant_id: Optional[str] = None, redirect_uri: Optional[str] = None) -> str:
        """Convenience method to get authorization URL (compatible with sync router)"""
        result = self.create_auth_url(tenant_id, redirect_uri)
        return result["auth_url"]

    async def exchange_code_for_tokens(self, code: str, redirect_uri: Optional[str] = None) -> Dict[str, str]:
        """Convenience method to exchange code for tokens (compatible with sync router)"""
        return await self.exchange_code(code, redirect_uri)

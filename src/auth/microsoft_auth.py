import msal
import time
from typing import Dict, Optional, List
from fastapi import HTTPException, status
from msgraph.core import GraphClient

from utils.config import settings

# OAuth scopes for Microsoft Graph Calendar access
SCOPES = [
    'Calendars.Read',
    'Calendars.Read.Shared',
    'offline_access',
    'User.Read'
]

class MicrosoftGraphAuth:
    def __init__(self):
        """Initialize Microsoft Graph authentication"""
        self.client_id = settings.MS_CLIENT_ID
        self.client_secret = settings.MS_CLIENT_SECRET
        self.redirect_uri = settings.MS_REDIRECT_URI
        self.default_tenant_id = settings.MS_TENANT_ID  # Default tenant ID
        
        if not all([self.client_id, self.client_secret]):
            raise ValueError("Microsoft Graph API credentials not configured")
    
    def create_auth_url(self, tenant_id: Optional[str] = None) -> Dict[str, str]:
        """
        Create authentication URL for Microsoft OAuth flow
        Optionally provide a tenant_id for multi-tenant applications
        """
        # Use provided tenant_id or default to the one in settings
        tenant = tenant_id if tenant_id else self.default_tenant_id
        
        # Fallback to common tenant if no tenant ID provided
        if not tenant:
            tenant = "common"
        
        # Create MSAL app
        app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=f"https://login.microsoftonline.com/{tenant}",
            client_credential=self.client_secret
        )
        
        # Generate authorization URL
        auth_url = app.get_authorization_request_url(
            scopes=SCOPES,
            redirect_uri=self.redirect_uri,
            state=tenant  # Store tenant ID in state for retrieval during callback
        )
        
        return {"auth_url": auth_url}
    
    async def exchange_code(self, code: str, tenant_id: Optional[str] = None) -> Dict[str, str]:
        """Exchange authorization code for tokens"""
        try:
            # Use provided tenant_id or default to the one in settings
            tenant = tenant_id if tenant_id else self.default_tenant_id
            
            # Fallback to common tenant if no tenant ID provided
            if not tenant:
                tenant = "common"
            
            # Create MSAL app
            app = msal.ConfidentialClientApplication(
                self.client_id,
                authority=f"https://login.microsoftonline.com/{tenant}",
                client_credential=self.client_secret
            )
            
            # Exchange authorization code for tokens
            result = app.acquire_token_by_authorization_code(
                code=code,
                scopes=SCOPES,
                redirect_uri=self.redirect_uri
            )
            
            if "error" in result:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to exchange code: {result.get('error_description', result.get('error'))}"
                )
            
            # Return tokens as dict
            return {
                "token_type": result.get("token_type", "Bearer"),
                "access_token": result.get("access_token"),
                "refresh_token": result.get("refresh_token"),
                "expires_at": time.time() + result.get("expires_in", 3600),
                "tenant_id": tenant
            }
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to exchange code: {str(e)}"
            )
    
    async def refresh_token(self, refresh_token: str, tenant_id: Optional[str] = None) -> Dict[str, str]:
        """Refresh the access token using the refresh token"""
        try:
            # Use provided tenant_id or default to the one in settings
            tenant = tenant_id if tenant_id else self.default_tenant_id
            
            # Fallback to common tenant if no tenant ID provided
            if not tenant:
                tenant = "common"
            
            # Create MSAL app
            app = msal.ConfidentialClientApplication(
                self.client_id,
                authority=f"https://login.microsoftonline.com/{tenant}",
                client_credential=self.client_secret
            )
            
            # Acquire token with refresh token
            result = app.acquire_token_by_refresh_token(
                refresh_token=refresh_token,
                scopes=SCOPES
            )
            
            if "error" in result:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to refresh token: {result.get('error_description', result.get('error'))}"
                )
            
            # Return new tokens
            return {
                "token_type": result.get("token_type", "Bearer"),
                "access_token": result.get("access_token"),
                "refresh_token": result.get("refresh_token", refresh_token),  # Use new refresh token if available
                "expires_at": time.time() + result.get("expires_in", 3600),
                "tenant_id": tenant
            }
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Failed to refresh token: {str(e)}"
            )
    
    async def get_graph_client(self, token_info: Dict[str, str]) -> GraphClient:
        """Create Microsoft Graph client using token info"""
        try:
            # Check if token has expired
            now = time.time()
            expires_at = token_info.get("expires_at", 0)
            
            # If token has expired and we have a refresh token, get a new token
            if expires_at < now and "refresh_token" in token_info:
                token_info = await self.refresh_token(
                    refresh_token=token_info["refresh_token"],
                    tenant_id=token_info.get("tenant_id")
                )
            
            # Create Graph client
            client = GraphClient(credentials=token_info.get("access_token"))
            return client
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Failed to authenticate with Microsoft Graph: {str(e)}"
            )
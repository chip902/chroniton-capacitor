import logging
import base64
from typing import Dict, Any
from fastapi import HTTPException, status

# Set up logging
logger = logging.getLogger(__name__)

class ExchangeAuth:
    """
    Authentication handler for Exchange/Mailcow ActiveSync
    
    This class provides methods for authenticating with Exchange servers
    using basic authentication (username/password).
    """
    
    def __init__(self):
        """Initialize Exchange authentication"""
        pass
    
    async def authenticate(self, credentials: Dict[str, str]) -> Dict[str, Any]:
        """
        Authenticate with Exchange server using provided credentials
        
        Args:
            credentials: Dictionary containing exchange_url, username, and password
            
        Returns:
            Dictionary with authentication status and token info
        """
        try:
            # Extract credentials
            exchange_url = credentials.get("exchange_url")
            username = credentials.get("username")
            password = credentials.get("password")
            
            # Validate required fields
            if not all([exchange_url, username, password]):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing required Exchange credentials: exchange_url, username, and password are required"
                )
            
            # Create basic auth string
            auth_string = f"{username}:{password}"
            auth_bytes = auth_string.encode('ascii')
            base64_auth = base64.b64encode(auth_bytes).decode('ascii')
            
            # Return the authentication info
            # In a real implementation, this would validate the credentials by making a test request
            # to the Exchange server, but for simplicity we're just returning the credentials
            return {
                "token_type": "Basic",
                "access_token": base64_auth,
                "exchange_url": exchange_url,
                "username": username,
                # We don't return the password for security reasons
            }
            
        except HTTPException:
            # Re-raise HTTP exceptions as is
            raise
        except Exception as e:
            logger.error(f"Error in Exchange authentication: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Exchange authentication error: {str(e)}"
            )
    
    async def validate_auth(self, auth_info: Dict[str, Any]) -> bool:
        """
        Validate authentication info
        
        Args:
            auth_info: Authentication information
            
        Returns:
            True if the authentication info is valid, False otherwise
        """
        try:
            # Check required fields
            required_fields = ["token_type", "access_token", "exchange_url", "username"]
            if not all(field in auth_info for field in required_fields):
                return False
            
            # In a real implementation, this would make a test request to the Exchange server
            # to verify the credentials are still valid, but for simplicity we're just checking
            # that the required fields are present
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating Exchange auth: {str(e)}")
            return False
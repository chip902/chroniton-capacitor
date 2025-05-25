from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Dict, Any, Optional

from auth.exchange_auth import ExchangeAuth

# Define the router
router = APIRouter(tags=["Exchange"])

# Define request models
class ExchangeAuthRequest(BaseModel):
    exchange_url: str
    username: str
    password: str

# Initialize authentication
exchange_auth = ExchangeAuth()

@router.post("/auth/exchange", response_model=Dict[str, Any])
async def authenticate_exchange(auth_request: ExchangeAuthRequest):
    """
    Authenticate with Exchange/Mailcow ActiveSync server
    
    This endpoint authenticates with an Exchange server using basic authentication
    (username/password). It does not use OAuth like the other providers.
    
    Args:
        auth_request: Exchange authentication request with server URL, username, and password
        
    Returns:
        Authentication info including access token
    """
    try:
        # Authenticate with Exchange
        auth_info = await exchange_auth.authenticate({
            "exchange_url": auth_request.exchange_url,
            "username": auth_request.username,
            "password": auth_request.password
        })
        
        return auth_info
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Exchange authentication error: {str(e)}"
        )

@router.get("/auth/exchange/validate", response_model=Dict[str, Any])
async def validate_exchange_auth(
    exchange_url: str,
    access_token: str,
    username: str
):
    """
    Validate Exchange authentication
    
    This endpoint validates Exchange authentication by checking if the
    provided credentials are still valid.
    
    Args:
        exchange_url: Exchange server URL
        access_token: Base64 encoded authentication token
        username: Exchange username
        
    Returns:
        Validation status
    """
    try:
        # Validate authentication
        is_valid = await exchange_auth.validate_auth({
            "token_type": "Basic",
            "access_token": access_token,
            "exchange_url": exchange_url,
            "username": username
        })
        
        if is_valid:
            return {"status": "valid"}
        else:
            return {"status": "invalid"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Exchange authentication validation error: {str(e)}"
        )
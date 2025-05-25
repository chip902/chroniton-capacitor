import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta

from services.exchange_calendar import ExchangeCalendarService
from services.calendar_event import CalendarEvent, CalendarProvider

@pytest.fixture
def exchange_service():
    """Create a test instance of the ExchangeCalendarService"""
    return ExchangeCalendarService()

@pytest.fixture
def mock_credentials():
    """Create mock Exchange credentials"""
    return {
        "exchange_url": "https://exchange.example.com",
        "username": "test_user",
        "password": "test_password"
    }

@pytest.fixture
def mock_auth_info():
    """Create mock authentication info"""
    return {
        "token_type": "Basic",
        "access_token": "dGVzdF91c2VyOnRlc3RfcGFzc3dvcmQ=",  # base64 of test_user:test_password
        "exchange_url": "https://exchange.example.com",
        "username": "test_user"
    }

@pytest.mark.asyncio
async def test_authenticate(exchange_service, mock_credentials):
    """Test the authenticate method"""
    # Mock the requests module
    with patch('services.exchange_calendar.requests.get') as mock_get:
        # Configure the mock
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        # Call the authenticate method
        auth_info = await exchange_service.authenticate(mock_credentials)
        
        # Verify the result
        assert auth_info["status"] == "authenticated"
        assert auth_info["auth_type"] == "basic"
        assert auth_info["exchange_url"] == mock_credentials["exchange_url"]
        assert auth_info["username"] == mock_credentials["username"]
        
        # Verify that the request was made with the correct parameters
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert kwargs["headers"]["Authorization"].startswith("Basic ")

@pytest.mark.asyncio
async def test_list_calendars(exchange_service, mock_auth_info):
    """Test the list_calendars method"""
    # Mock the requests module
    with patch('services.exchange_calendar.requests.post') as mock_post:
        # Configure the mock
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        # Call the list_calendars method
        calendars = await exchange_service.list_calendars(mock_auth_info)
        
        # Verify the result
        assert len(calendars) > 0
        assert isinstance(calendars, list)
        assert "id" in calendars[0]
        assert "name" in calendars[0]
        assert "color" in calendars[0]
        
        # Verify that the request was made with the correct parameters
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert kwargs["headers"]["Authorization"] == f"Basic {mock_auth_info['access_token']}"

@pytest.mark.asyncio
async def test_get_events(exchange_service, mock_auth_info):
    """Test the get_events method"""
    # Mock the requests module
    with patch('services.exchange_calendar.requests.post') as mock_post:
        # Configure the mock
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        # Set up test parameters
        calendar_id = "default"
        start_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=7)
        
        # Call the get_events method
        result = await exchange_service.get_events(
            mock_auth_info,
            calendar_id,
            start_date,
            end_date
        )
        
        # Verify the result
        assert "events" in result
        assert len(result["events"]) > 0
        assert isinstance(result["events"][0], CalendarEvent)
        assert result["events"][0].provider == CalendarProvider.EXCHANGE
        assert "syncToken" in result
        
        # Verify that the request was made with the correct parameters
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert kwargs["headers"]["Authorization"] == f"Basic {mock_auth_info['access_token']}"
        assert calendar_id in kwargs["data"]
        assert start_date.strftime("%Y-%m-%dT%H:%M:%SZ") in kwargs["data"]
        assert end_date.strftime("%Y-%m-%dT%H:%M:%SZ") in kwargs["data"]
import logging
import base64
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from urllib.parse import urlparse

from services.calendar_event import CalendarEvent, CalendarProvider

# Set up logging
logger = logging.getLogger(__name__)

class ExchangeCalendarService:
    """
    Calendar service for Exchange/Mailcow ActiveSync integration
    
    This service provides integration with Exchange servers including Mailcow
    ActiveSync calendars using the Exchange Web Services (EWS) API.
    """
    
    def __init__(self):
        """Initialize the Exchange Calendar service"""
        pass
        
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry_if_exception_type(Exception),
        reraise=True
    )
    async def authenticate(self, credentials: Dict[str, str]) -> Dict[str, Any]:
        """
        Authenticate with Exchange server
        
        Args:
            credentials: Dictionary containing exchange_url, username, and password
            
        Returns:
            Dictionary with authentication status and session info
        """
        try:
            # Extract credentials
            exchange_url = credentials.get("exchange_url")
            username = credentials.get("username")
            password = credentials.get("password")
            
            if not all([exchange_url, username, password]):
                raise ValueError("Missing required Exchange credentials")
            
            # Parse the Exchange URL to ensure it's valid
            parsed_url = urlparse(exchange_url)
            if not parsed_url.scheme or not parsed_url.netloc:
                raise ValueError("Invalid Exchange server URL")
            
            # Create basic auth credentials
            auth_string = f"{username}:{password}"
            auth_bytes = auth_string.encode('ascii')
            base64_auth = base64.b64encode(auth_bytes).decode('ascii')
            
            # Test connection with the Exchange server
            headers = {
                'Authorization': f'Basic {base64_auth}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            # Try to get server info - this will vary based on the specific
            # Exchange/Mailcow implementation
            server_info_url = f"{exchange_url}/ews/exchange.asmx"
            response = requests.get(
                server_info_url,
                headers=headers,
                timeout=30
            )
            
            # If we get a 401, the credentials are invalid
            if response.status_code == 401:
                raise ValueError("Invalid Exchange credentials")
            
            # Store the auth credentials for future use
            return {
                "status": "authenticated",
                "auth_type": "basic",
                "auth_string": base64_auth,
                "exchange_url": exchange_url,
                "username": username
            }
            
        except Exception as e:
            logger.error(f"Error authenticating with Exchange server: {e}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry_if_exception_type(Exception),
        reraise=True
    )
    async def list_calendars(self, auth_info: Dict[str, str]) -> List[Dict[str, Any]]:
        """
        List available calendars for the authenticated user
        
        Args:
            auth_info: Authentication information from authenticate method
            
        Returns:
            List of calendar dictionaries
        """
        try:
            # Get auth information
            exchange_url = auth_info.get("exchange_url")
            auth_string = auth_info.get("auth_string")
            
            if not all([exchange_url, auth_string]):
                raise ValueError("Missing required Exchange authentication info")
            
            # Set up headers
            headers = {
                'Authorization': f'Basic {auth_string}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            # Build SOAP request for FindFolder operation
            # This is a simplified version and may need to be adjusted for specific Exchange versions
            soap_request = """
            <?xml version="1.0" encoding="utf-8"?>
            <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
                           xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types"
                           xmlns:m="http://schemas.microsoft.com/exchange/services/2006/messages">
              <soap:Header>
                <t:RequestServerVersion Version="Exchange2013" />
              </soap:Header>
              <soap:Body>
                <m:FindFolder Traversal="Deep">
                  <m:FolderShape>
                    <t:BaseShape>AllProperties</t:BaseShape>
                  </m:FolderShape>
                  <m:ParentFolderIds>
                    <t:DistinguishedFolderId Id="calendar"/>
                  </m:ParentFolderIds>
                </m:FindFolder>
              </soap:Body>
            </soap:Envelope>
            """
            
            # Send SOAP request to Exchange server
            calendar_url = f"{exchange_url}/ews/exchange.asmx"
            response = requests.post(
                calendar_url,
                headers={
                    'Authorization': f'Basic {auth_string}',
                    'Content-Type': 'text/xml; charset=utf-8',
                    'Accept': 'text/xml'
                },
                data=soap_request,
                timeout=30
            )
            
            # Parse the XML response to extract calendar information
            # This is simplified and would need to be expanded for production use
            # In a real implementation, use an XML parser to process the response
            
            # For demonstration, we'll return a default calendar
            # In a real implementation, you would parse the XML response
            calendars = [{
                'id': 'default',
                'name': 'Default Calendar',
                'color': 'blue',
                'hexColor': '#4285F4',
                'canShare': True,
                'canViewPrivateItems': True,
                'isDefaultCalendar': True,
                'owner': auth_info.get("username", "")
            }]
            
            return calendars
            
        except Exception as e:
            logger.error(f"Error listing Exchange calendars: {e}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry_if_exception_type(Exception),
        reraise=True
    )
    async def get_events(
        self,
        auth_info: Dict[str, str],
        calendar_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        max_results: int = 100,
        sync_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get events from a specific Exchange calendar
        
        Args:
            auth_info: Authentication information from authenticate method
            calendar_id: ID of the calendar to fetch events from
            start_date: Start date for events (defaults to today)
            end_date: End date for events (defaults to 30 days from start)
            max_results: Maximum number of events to return
            sync_token: Token from previous sync to get only changes
            
        Returns:
            Dictionary with events and next sync token
        """
        try:
            # Get auth information
            exchange_url = auth_info.get("exchange_url")
            auth_string = auth_info.get("auth_string")
            
            if not all([exchange_url, auth_string]):
                raise ValueError("Missing required Exchange authentication info")
            
            # Set default dates if not provided
            if not start_date:
                start_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            
            if not end_date:
                end_date = start_date + timedelta(days=30)
            
            # Format dates for Exchange API
            start_str = start_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            end_str = end_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            
            # Build SOAP request for FindItem operation
            # This is a simplified version and may need to be adjusted for specific Exchange versions
            soap_request = f"""
            <?xml version="1.0" encoding="utf-8"?>
            <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
                           xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types"
                           xmlns:m="http://schemas.microsoft.com/exchange/services/2006/messages">
              <soap:Header>
                <t:RequestServerVersion Version="Exchange2013" />
              </soap:Header>
              <soap:Body>
                <m:FindItem Traversal="Shallow">
                  <m:ItemShape>
                    <t:BaseShape>AllProperties</t:BaseShape>
                  </m:ItemShape>
                  <m:CalendarView StartDate="{start_str}" EndDate="{end_str}" MaxEntriesReturned="{max_results}" />
                  <m:ParentFolderIds>
                    <t:FolderId Id="{calendar_id}" />
                  </m:ParentFolderIds>
                </m:FindItem>
              </soap:Body>
            </soap:Envelope>
            """
            
            # Send SOAP request to Exchange server
            calendar_url = f"{exchange_url}/ews/exchange.asmx"
            response = requests.post(
                calendar_url,
                headers={
                    'Authorization': f'Basic {auth_string}',
                    'Content-Type': 'text/xml; charset=utf-8',
                    'Accept': 'text/xml'
                },
                data=soap_request,
                timeout=30
            )
            
            # Parse the XML response to extract event information
            # This is simplified and would need to be expanded for production use
            # In a real implementation, use an XML parser to process the response
            
            # For demonstration, we'll return a sample event
            # In a real implementation, you would parse the XML response
            sample_event = {
                'id': 'sample-event-id',
                'subject': 'Sample Exchange Event',
                'bodyPreview': 'This is a sample event for testing purposes',
                'start': {
                    'dateTime': start_date.isoformat(),
                    'timeZone': 'UTC'
                },
                'end': {
                    'dateTime': (start_date + timedelta(hours=1)).isoformat(),
                    'timeZone': 'UTC'
                },
                'location': {
                    'displayName': 'Conference Room'
                },
                'organizer': {
                    'emailAddress': {
                        'name': 'Organizer Name',
                        'address': 'organizer@example.com'
                    }
                },
                'attendees': [
                    {
                        'emailAddress': {
                            'name': 'Attendee 1',
                            'address': 'attendee1@example.com'
                        },
                        'status': {
                            'response': 'accepted'
                        }
                    }
                ],
                'isAllDay': False,
                'isCancelled': False,
                'sensitivity': 'normal',
                'showAs': 'busy',
                'createdDateTime': (datetime.utcnow() - timedelta(days=1)).isoformat(),
                'lastModifiedDateTime': datetime.utcnow().isoformat()
            }
            
            # Create a normalized event
            normalized_event = CalendarEvent.from_exchange(
                sample_event,
                calendar_id,
                "Default Calendar"
            )
            
            # Return the events and a dummy sync token
            return {
                'events': [normalized_event],
                'syncToken': 'exchange-dummy-sync-token',
                'provider': CalendarProvider.EXCHANGE
            }
            
        except Exception as e:
            logger.error(f"Error getting Exchange calendar events: {e}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry_if_exception_type(Exception),
        reraise=True
    )
    async def create_event(
        self,
        auth_info: Dict[str, str],
        calendar_id: str,
        event: CalendarEvent
    ) -> Dict[str, Any]:
        """
        Create a new event in an Exchange calendar
        
        Args:
            auth_info: Authentication information from authenticate method
            calendar_id: ID of the calendar to create the event in
            event: The event to create
            
        Returns:
            The created event
        """
        try:
            # Get auth information
            exchange_url = auth_info.get("exchange_url")
            auth_string = auth_info.get("auth_string")
            
            if not all([exchange_url, auth_string]):
                raise ValueError("Missing required Exchange authentication info")
            
            # Format event dates
            start_str = event.start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            end_str = event.end_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            
            # Build SOAP request for CreateItem operation
            soap_request = f"""
            <?xml version="1.0" encoding="utf-8"?>
            <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
                           xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types"
                           xmlns:m="http://schemas.microsoft.com/exchange/services/2006/messages">
              <soap:Header>
                <t:RequestServerVersion Version="Exchange2013" />
              </soap:Header>
              <soap:Body>
                <m:CreateItem SendMeetingInvitations="SendToAllAndSaveCopy">
                  <m:Items>
                    <t:CalendarItem>
                      <t:Subject>{event.title}</t:Subject>
                      <t:Body BodyType="Text">{event.description or ''}</t:Body>
                      <t:Start>{start_str}</t:Start>
                      <t:End>{end_str}</t:End>
                      <t:Location>{event.location or ''}</t:Location>
                      <t:IsAllDayEvent>{str(event.all_day).lower()}</t:IsAllDayEvent>
                    </t:CalendarItem>
                  </m:Items>
                  <m:SavedItemFolderId>
                    <t:FolderId Id="{calendar_id}" />
                  </m:SavedItemFolderId>
                </m:CreateItem>
              </soap:Body>
            </soap:Envelope>
            """
            
            # Send SOAP request to Exchange server
            calendar_url = f"{exchange_url}/ews/exchange.asmx"
            response = requests.post(
                calendar_url,
                headers={
                    'Authorization': f'Basic {auth_string}',
                    'Content-Type': 'text/xml; charset=utf-8',
                    'Accept': 'text/xml'
                },
                data=soap_request,
                timeout=30
            )
            
            # Parse the XML response to extract the created event ID
            # This is simplified and would need to be expanded for production use
            
            # Return the event with a dummy ID
            return {
                'id': 'new-exchange-event-id',
                'status': 'created',
                'event': event
            }
            
        except Exception as e:
            logger.error(f"Error creating Exchange calendar event: {e}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry_if_exception_type(Exception),
        reraise=True
    )
    async def update_event(
        self,
        auth_info: Dict[str, str],
        calendar_id: str,
        event_id: str,
        event: CalendarEvent
    ) -> Dict[str, Any]:
        """
        Update an existing event in an Exchange calendar
        
        Args:
            auth_info: Authentication information from authenticate method
            calendar_id: ID of the calendar containing the event
            event_id: ID of the event to update
            event: The updated event data
            
        Returns:
            The updated event
        """
        try:
            # Get auth information
            exchange_url = auth_info.get("exchange_url")
            auth_string = auth_info.get("auth_string")
            
            if not all([exchange_url, auth_string]):
                raise ValueError("Missing required Exchange authentication info")
            
            # Format event dates
            start_str = event.start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            end_str = event.end_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            
            # Build SOAP request for UpdateItem operation
            soap_request = f"""
            <?xml version="1.0" encoding="utf-8"?>
            <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
                           xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types"
                           xmlns:m="http://schemas.microsoft.com/exchange/services/2006/messages">
              <soap:Header>
                <t:RequestServerVersion Version="Exchange2013" />
              </soap:Header>
              <soap:Body>
                <m:UpdateItem ConflictResolution="AutoResolve" SendMeetingInvitationsOrCancellations="SendToAllAndSaveCopy">
                  <m:ItemChanges>
                    <t:ItemChange>
                      <t:ItemId Id="{event_id}" />
                      <t:Updates>
                        <t:SetItemField>
                          <t:FieldURI FieldURI="item:Subject" />
                          <t:CalendarItem>
                            <t:Subject>{event.title}</t:Subject>
                          </t:CalendarItem>
                        </t:SetItemField>
                        <t:SetItemField>
                          <t:FieldURI FieldURI="calendar:Start" />
                          <t:CalendarItem>
                            <t:Start>{start_str}</t:Start>
                          </t:CalendarItem>
                        </t:SetItemField>
                        <t:SetItemField>
                          <t:FieldURI FieldURI="calendar:End" />
                          <t:CalendarItem>
                            <t:End>{end_str}</t:End>
                          </t:CalendarItem>
                        </t:SetItemField>
                        <t:SetItemField>
                          <t:FieldURI FieldURI="calendar:Location" />
                          <t:CalendarItem>
                            <t:Location>{event.location or ''}</t:Location>
                          </t:CalendarItem>
                        </t:SetItemField>
                      </t:Updates>
                    </t:ItemChange>
                  </m:ItemChanges>
                </m:UpdateItem>
              </soap:Body>
            </soap:Envelope>
            """
            
            # Send SOAP request to Exchange server
            calendar_url = f"{exchange_url}/ews/exchange.asmx"
            response = requests.post(
                calendar_url,
                headers={
                    'Authorization': f'Basic {auth_string}',
                    'Content-Type': 'text/xml; charset=utf-8',
                    'Accept': 'text/xml'
                },
                data=soap_request,
                timeout=30
            )
            
            # Parse the XML response to confirm the update
            # This is simplified and would need to be expanded for production use
            
            # Return the updated event
            return {
                'id': event_id,
                'status': 'updated',
                'event': event
            }
            
        except Exception as e:
            logger.error(f"Error updating Exchange calendar event: {e}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry_if_exception_type(Exception),
        reraise=True
    )
    async def delete_event(
        self,
        auth_info: Dict[str, str],
        calendar_id: str,
        event_id: str
    ) -> Dict[str, Any]:
        """
        Delete an event from an Exchange calendar
        
        Args:
            auth_info: Authentication information from authenticate method
            calendar_id: ID of the calendar containing the event
            event_id: ID of the event to delete
            
        Returns:
            Status of the deletion
        """
        try:
            # Get auth information
            exchange_url = auth_info.get("exchange_url")
            auth_string = auth_info.get("auth_string")
            
            if not all([exchange_url, auth_string]):
                raise ValueError("Missing required Exchange authentication info")
            
            # Build SOAP request for DeleteItem operation
            soap_request = f"""
            <?xml version="1.0" encoding="utf-8"?>
            <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
                           xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types"
                           xmlns:m="http://schemas.microsoft.com/exchange/services/2006/messages">
              <soap:Header>
                <t:RequestServerVersion Version="Exchange2013" />
              </soap:Header>
              <soap:Body>
                <m:DeleteItem DeleteType="MoveToDeletedItems" SendMeetingCancellations="SendToAllAndSaveCopy">
                  <m:ItemIds>
                    <t:ItemId Id="{event_id}" />
                  </m:ItemIds>
                </m:DeleteItem>
              </soap:Body>
            </soap:Envelope>
            """
            
            # Send SOAP request to Exchange server
            calendar_url = f"{exchange_url}/ews/exchange.asmx"
            response = requests.post(
                calendar_url,
                headers={
                    'Authorization': f'Basic {auth_string}',
                    'Content-Type': 'text/xml; charset=utf-8',
                    'Accept': 'text/xml'
                },
                data=soap_request,
                timeout=30
            )
            
            # Parse the XML response to confirm the deletion
            # This is simplified and would need to be expanded for production use
            
            # Return the deletion status
            return {
                'id': event_id,
                'status': 'deleted'
            }
            
        except Exception as e:
            logger.error(f"Error deleting Exchange calendar event: {e}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry_if_exception_type(Exception),
        reraise=True
    )
    async def create_calendar(
        self,
        auth_info: Dict[str, str],
        name: str,
        color: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new calendar in Exchange
        
        Args:
            auth_info: Authentication information from authenticate method
            name: Name of the calendar to create
            color: Color for the calendar (hex code)
            
        Returns:
            The created calendar
        """
        try:
            # Get auth information
            exchange_url = auth_info.get("exchange_url")
            auth_string = auth_info.get("auth_string")
            
            if not all([exchange_url, auth_string]):
                raise ValueError("Missing required Exchange authentication info")
            
            # Build SOAP request for CreateFolder operation
            soap_request = f"""
            <?xml version="1.0" encoding="utf-8"?>
            <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
                           xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types"
                           xmlns:m="http://schemas.microsoft.com/exchange/services/2006/messages">
              <soap:Header>
                <t:RequestServerVersion Version="Exchange2013" />
              </soap:Header>
              <soap:Body>
                <m:CreateFolder>
                  <m:ParentFolderIds>
                    <t:DistinguishedFolderId Id="calendar"/>
                  </m:ParentFolderIds>
                  <m:Folders>
                    <t:CalendarFolder>
                      <t:DisplayName>{name}</t:DisplayName>
                    </t:CalendarFolder>
                  </m:Folders>
                </m:CreateFolder>
              </soap:Body>
            </soap:Envelope>
            """
            
            # Send SOAP request to Exchange server
            calendar_url = f"{exchange_url}/ews/exchange.asmx"
            response = requests.post(
                calendar_url,
                headers={
                    'Authorization': f'Basic {auth_string}',
                    'Content-Type': 'text/xml; charset=utf-8',
                    'Accept': 'text/xml'
                },
                data=soap_request,
                timeout=30
            )
            
            # Parse the XML response to extract the created calendar ID
            # This is simplified and would need to be expanded for production use
            
            # Return the calendar with a dummy ID
            return {
                'id': 'new-exchange-calendar-id',
                'name': name,
                'color': color or 'blue',
                'hexColor': color or '#4285F4',
                'canShare': True,
                'canViewPrivateItems': True,
                'isDefaultCalendar': False,
                'owner': auth_info.get("username", "")
            }
            
        except Exception as e:
            logger.error(f"Error creating Exchange calendar: {e}")
            raise
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from auth.microsoft_auth import MicrosoftGraphAuth
from services.calendar_event import CalendarEvent, CalendarProvider

# Set up logging
logger = logging.getLogger(__name__)

class MicrosoftCalendarService:
    def __init__(self):
        """Initialize the Microsoft Calendar service"""
        self.auth = MicrosoftGraphAuth()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry_if_exception_type(Exception),
        reraise=True
    )
    async def list_calendars(self, token_info: Dict[str, str]) -> List[Dict[str, Any]]:
        """List available calendars for the authenticated user"""
        try:
            # Get Microsoft Graph client
            client = await self.auth.get_graph_client(token_info)
            
            # Get calendar list
            response = await client.get('/me/calendars')
            calendar_list = response.json()
            
            # Format response
            calendars = []
            for calendar in calendar_list.get('value', []):
                calendars.append({
                    'id': calendar['id'],
                    'name': calendar.get('name', 'Unnamed Calendar'),
                    'color': calendar.get('color', ''),
                    'hexColor': calendar.get('hexColor', ''),
                    'canShare': calendar.get('canShare', False),
                    'canViewPrivateItems': calendar.get('canViewPrivateItems', False),
                    'isDefaultCalendar': calendar.get('isDefaultCalendar', False),
                    'owner': calendar.get('owner', {}).get('name', '')
                })
                
            return calendars
            
        except Exception as e:
            logger.error(f"Error listing Microsoft calendars: {e}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry_if_exception_type(Exception),
        reraise=True
    )
    async def get_events(
        self, 
        token_info: Dict[str, str], 
        calendar_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        max_results: int = 100,
        delta_link: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get events from a specific Microsoft calendar
        
        Args:
            token_info: Microsoft OAuth tokens
            calendar_id: ID of the calendar to fetch events from
            start_date: Start date for events (defaults to today)
            end_date: End date for events (defaults to 30 days from start)
            max_results: Maximum number of events to return
            delta_link: URL from previous sync to get only changes
            
        Returns:
            Dictionary with events and next delta link
        """
        try:
            # Get Microsoft Graph client
            client = await self.auth.get_graph_client(token_info)
            
            # Set default dates if not provided
            if not start_date:
                start_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            
            if not end_date:
                end_date = start_date + timedelta(days=30)
            
            # Format dates for Microsoft Graph API
            start_filter = start_date.isoformat() + 'Z'
            end_filter = end_date.isoformat() + 'Z'
            
            # Use delta link or regular query
            if delta_link:
                # Use the delta link directly
                response = await client.get(delta_link)
            else:
                # Query events within the time range
                filter_query = f"start/dateTime ge '{start_filter}' and end/dateTime le '{end_filter}'"
                select_query = "id,subject,bodyPreview,importance,sensitivity,start,end,location,organizer,attendees,isAllDay,isCancelled,recurrence,webLink,createdDateTime,lastModifiedDateTime"
                
                url = f"/me/calendars/{calendar_id}/events/delta"
                response = await client.get(
                    url,
                    params={
                        "$filter": filter_query,
                        "$select": select_query,
                        "$top": max_results
                    }
                )
            
            # Process the response
            data = response.json()
            events_data = data.get('value', [])
            
            # Get calendar details
            calendar_response = await client.get(f"/me/calendars/{calendar_id}")
            calendar_details = calendar_response.json()
            calendar_name = calendar_details.get('name', 'Unknown Calendar')
            
            # Process events
            normalized_events = []
            for event in events_data:
                try:
                    normalized_events.append(
                        CalendarEvent.from_microsoft(event, calendar_id, calendar_name)
                    )
                except Exception as event_error:
                    logger.error(f"Error processing Microsoft event {event.get('id')}: {event_error}")
                    # Continue with next event
                    continue
            
            # Extract the delta link from @odata.nextLink or @odata.deltaLink
            next_link = data.get('@odata.nextLink')
            delta_link = data.get('@odata.deltaLink', next_link)
            
            # Return the events and delta link
            return {
                'events': normalized_events,
                'deltaLink': delta_link,
                'provider': CalendarProvider.MICROSOFT
            }
            
        except Exception as e:
            logger.error(f"Error getting Microsoft calendar events: {e}")
            
            # If delta link is causing issues, try again without it
            if delta_link:
                logger.info("Microsoft delta link may be invalid, fetching full data")
                return await self.get_events(
                    token_info=token_info,
                    calendar_id=calendar_id,
                    start_date=start_date,
                    end_date=end_date,
                    max_results=max_results,
                    delta_link=None  # Reset the delta link
                )
            
            raise
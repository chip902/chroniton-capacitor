import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from googleapiclient.errors import HttpError

from auth.google_auth import GoogleCalendarAuth
from services.calendar_event import CalendarEvent, CalendarProvider

# Set up logging
logger = logging.getLogger(__name__)

class GoogleCalendarService:
    def __init__(self):
        """Initialize the Google Calendar service"""
        self.auth = GoogleCalendarAuth()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(HttpError),
        reraise=True
    )
    async def list_calendars(self, token_info: Dict[str, str]) -> List[Dict[str, Any]]:
        """List available calendars for the authenticated user"""
        try:
            # Get Google Calendar service
            service = await self.auth.get_calendar_service(token_info)
            
            # Get calendar list
            calendar_list = service.calendarList().list().execute()
            
            # Format response
            calendars = []
            for calendar in calendar_list.get('items', []):
                calendars.append({
                    'id': calendar['id'],
                    'summary': calendar.get('summary', 'Unnamed Calendar'),
                    'description': calendar.get('description', ''),
                    'location': calendar.get('location', ''),
                    'timeZone': calendar.get('timeZone', 'UTC'),
                    'accessRole': calendar.get('accessRole', ''),
                    'primary': calendar.get('primary', False)
                })
                
            return calendars
            
        except HttpError as error:
            logger.error(f"Error listing Google calendars: {error}")
            # Let the retry decorator handle HttpErrors
            raise
        except Exception as e:
            logger.error(f"Unexpected error listing Google calendars: {e}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(HttpError),
        reraise=True
    )
    async def get_events(
        self, 
        token_info: Dict[str, str], 
        calendar_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        max_results: int = 100,
        sync_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get events from a specific Google calendar
        
        Args:
            token_info: Google OAuth tokens
            calendar_id: ID of the calendar to fetch events from
            start_date: Start date for events (defaults to today)
            end_date: End date for events (defaults to 30 days from start)
            max_results: Maximum number of events to return
            sync_token: Token from previous sync to get only changes
            
        Returns:
            Dictionary with events and next sync token
        """
        try:
            # Get Google Calendar service
            service = await self.auth.get_calendar_service(token_info)
            
            # Set default dates if not provided
            if not start_date:
                start_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            
            if not end_date:
                end_date = start_date + timedelta(days=30)
            
            # Format dates for Google API
            time_min = start_date.isoformat() + 'Z'
            time_max = end_date.isoformat() + 'Z'
            
            # Prepare request parameters
            params = {
                'maxResults': max_results,
                'orderBy': 'startTime',
                'singleEvents': True  # Expand recurring events
            }
            
            # Use sync token if provided, otherwise use time bounds
            if sync_token:
                params['syncToken'] = sync_token
            else:
                params['timeMin'] = time_min
                params['timeMax'] = time_max
            
            # Get events
            events_result = service.events().list(calendarId=calendar_id, **params).execute()
            
            # Get calendar details for mapping to events
            calendar_details = service.calendars().get(calendarId=calendar_id).execute()
            calendar_name = calendar_details.get('summary', 'Unknown Calendar')
            
            # Process events
            normalized_events = []
            for event in events_result.get('items', []):
                try:
                    normalized_events.append(
                        CalendarEvent.from_google(event, calendar_id, calendar_name)
                    )
                except Exception as event_error:
                    logger.error(f"Error processing Google event {event.get('id')}: {event_error}")
                    # Continue with next event
                    continue
            
            # Return the events and next sync token
            return {
                'events': normalized_events,
                'nextSyncToken': events_result.get('nextSyncToken', None),
                'provider': CalendarProvider.GOOGLE
            }
            
        except HttpError as error:
            # If sync token is invalid or expired, try again without it
            if error.status_code == 410 and sync_token:  # Gone - sync token expired
                logger.info("Google sync token expired, fetching full data")
                return await self.get_events(
                    token_info=token_info,
                    calendar_id=calendar_id,
                    start_date=start_date,
                    end_date=end_date,
                    max_results=max_results,
                    sync_token=None  # Reset the sync token
                )
            
            logger.error(f"Error getting Google calendar events: {error}")
            # Let the retry decorator handle other HttpErrors
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting Google calendar events: {e}")
            raise
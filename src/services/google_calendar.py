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

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(HttpError),
        reraise=True
    )
    async def create_event(
        self, 
        token_info: Dict[str, str], 
        calendar_id: str,
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a new event in Google Calendar
        
        Args:
            token_info: Google OAuth tokens
            calendar_id: ID of the calendar to create event in
            event_data: Event data in Google Calendar format
            
        Returns:
            Created event data
        """
        try:
            # Get Google Calendar service
            service = await self.auth.get_calendar_service(token_info)
            
            # Create the event
            created_event = service.events().insert(
                calendarId=calendar_id, 
                body=event_data
            ).execute()
            
            logger.info(f"Created event {created_event.get('id')} in calendar {calendar_id}")
            return created_event
            
        except HttpError as error:
            logger.error(f"Error creating Google calendar event: {error}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating Google calendar event: {e}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(HttpError),
        reraise=True
    )
    async def update_event(
        self, 
        token_info: Dict[str, str], 
        calendar_id: str,
        event_id: str,
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update an existing event in Google Calendar
        
        Args:
            token_info: Google OAuth tokens
            calendar_id: ID of the calendar containing the event
            event_id: ID of the event to update
            event_data: Updated event data in Google Calendar format
            
        Returns:
            Updated event data
        """
        try:
            # Get Google Calendar service
            service = await self.auth.get_calendar_service(token_info)
            
            # Update the event
            updated_event = service.events().update(
                calendarId=calendar_id,
                eventId=event_id,
                body=event_data
            ).execute()
            
            logger.info(f"Updated event {event_id} in calendar {calendar_id}")
            return updated_event
            
        except HttpError as error:
            logger.error(f"Error updating Google calendar event: {error}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error updating Google calendar event: {e}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(HttpError),
        reraise=True
    )
    async def delete_event(
        self, 
        token_info: Dict[str, str], 
        calendar_id: str,
        event_id: str
    ) -> bool:
        """
        Delete an event from Google Calendar
        
        Args:
            token_info: Google OAuth tokens
            calendar_id: ID of the calendar containing the event
            event_id: ID of the event to delete
            
        Returns:
            True if successful
        """
        try:
            # Get Google Calendar service
            service = await self.auth.get_calendar_service(token_info)
            
            # Delete the event
            service.events().delete(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            
            logger.info(f"Deleted event {event_id} from calendar {calendar_id}")
            return True
            
        except HttpError as error:
            if error.status_code == 404:
                logger.warning(f"Event {event_id} not found, considering it deleted")
                return True
            logger.error(f"Error deleting Google calendar event: {error}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error deleting Google calendar event: {e}")
            raise

    def convert_calendar_event_to_google_format(self, calendar_event: CalendarEvent) -> Dict[str, Any]:
        """
        Convert a CalendarEvent to Google Calendar API format
        
        Args:
            calendar_event: Normalized calendar event
            
        Returns:
            Event data in Google Calendar format
        """
        google_event = {
            'summary': calendar_event.title,
            'description': calendar_event.description or '',
            'location': calendar_event.location or '',
            'start': {},
            'end': {},
            'attendees': [],
            'status': 'confirmed'
        }
        
        # Handle start time
        if calendar_event.all_day:
            google_event['start']['date'] = calendar_event.start_time.date().isoformat()
            google_event['end']['date'] = calendar_event.end_time.date().isoformat()
        else:
            google_event['start']['dateTime'] = calendar_event.start_time.isoformat()
            google_event['end']['dateTime'] = calendar_event.end_time.isoformat()
            if hasattr(calendar_event, 'timezone') and calendar_event.timezone:
                google_event['start']['timeZone'] = calendar_event.timezone
                google_event['end']['timeZone'] = calendar_event.timezone
        
        # Handle attendees
        if calendar_event.participants:
            for participant in calendar_event.participants:
                if isinstance(participant, dict) and participant.get('email'):
                    attendee = {
                        'email': participant['email'],
                        'displayName': participant.get('name', ''),
                        'responseStatus': participant.get('status', 'needsAction')
                    }
                    google_event['attendees'].append(attendee)
        
        # Handle organizer
        if calendar_event.organizer and isinstance(calendar_event.organizer, dict):
            if calendar_event.organizer.get('email'):
                google_event['organizer'] = {
                    'email': calendar_event.organizer['email'],
                    'displayName': calendar_event.organizer.get('name', '')
                }
        
        # Handle recurring events
        if calendar_event.recurring and hasattr(calendar_event, 'recurrence_pattern'):
            if calendar_event.recurrence_pattern:
                google_event['recurrence'] = [f"RRULE:{calendar_event.recurrence_pattern}"]
        
        # Handle privacy
        if hasattr(calendar_event, 'private') and calendar_event.private:
            google_event['visibility'] = 'private'
        
        # Add source metadata
        google_event['extendedProperties'] = {
            'private': {
                'source_provider': calendar_event.provider.value if hasattr(calendar_event.provider, 'value') else str(calendar_event.provider),
                'source_calendar_id': calendar_event.calendar_id or '',
                'source_event_id': calendar_event.provider_id or calendar_event.id,
                'sync_timestamp': datetime.utcnow().isoformat()
            }
        }
        
        return google_event
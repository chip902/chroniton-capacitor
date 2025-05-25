"""
Apple Calendar Service

This module provides a service for integrating with Apple Calendar via the CalDAV protocol.
It provides the capability to:
1. List available calendars
2. Get events from calendars
3. Create/update/delete events in calendars
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
import uuid

# Try to import caldav library, handle gracefully if not installed
try:
    import caldav
    from caldav.elements import dav, cdav
    CALDAV_AVAILABLE = True
except ImportError:
    CALDAV_AVAILABLE = False
    logging.warning("caldav package not installed. Apple Calendar integration will be disabled.")

from services.calendar_event import CalendarEvent, CalendarProvider

# Set up logging
logger = logging.getLogger(__name__)

class AppleCalendarService:
    """Service for integrating with Apple Calendar via CalDAV"""
    
    def __init__(self):
        """Initialize the Apple Calendar service"""
        if not CALDAV_AVAILABLE:
            logger.warning("AppleCalendarService initialized but caldav package is not available.")
    
    async def connect(self, token_info: Dict[str, Any]) -> Any:
        """Connect to CalDAV server using credentials"""
        if not CALDAV_AVAILABLE:
            raise ImportError("caldav package is required for Apple Calendar integration")
            
        try:
            # Extract connection information from token_info
            url = token_info.get("url", "https://caldav.icloud.com")
            username = token_info.get("username")
            password = token_info.get("password")
            
            if not username or not password:
                raise ValueError("Username and password are required for Apple Calendar integration")
                
            # Create a DAV client
            # This needs to be run in a thread as caldav operations are blocking
            client = await asyncio.to_thread(
                caldav.DAVClient,
                url=url,
                username=username,
                password=password
            )
            
            return client
        except Exception as e:
            logger.error(f"Error connecting to Apple Calendar: {e}")
            raise
    
    async def list_calendars(self, token_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """List available calendars for the user"""
        try:
            # Connect to CalDAV server
            client = await self.connect(token_info)
            
            # Get principal (user)
            principal = await asyncio.to_thread(client.principal)
            
            # Get calendars
            calendars = await asyncio.to_thread(principal.calendars)
            
            # Convert to normalized format
            result = []
            for calendar in calendars:
                cal_info = {
                    "id": calendar.id,
                    "name": getattr(calendar, "name", calendar.id),
                    "description": getattr(calendar, "description", None),
                    "timezone": getattr(calendar, "timezone", None),
                    "color": None  # CalDAV doesn't have standardized color property
                }
                result.append(cal_info)
                
            return result
            
        except Exception as e:
            logger.error(f"Error listing Apple calendars: {e}")
            raise
    
    async def get_events(
        self,
        token_info: Dict[str, Any],
        calendar_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        max_results: int = 100,
        delta_link: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get events from Apple Calendar"""
        try:
            # Connect to CalDAV server
            client = await self.connect(token_info)
            
            # Get principal (user)
            principal = await asyncio.to_thread(client.principal)
            
            # Find the calendar by ID
            calendar = None
            calendars = await asyncio.to_thread(principal.calendars)
            for cal in calendars:
                if cal.id == calendar_id:
                    calendar = cal
                    break
            
            if not calendar:
                raise ValueError(f"Calendar with ID {calendar_id} not found")
            
            # Set default date range if not provided
            if not start_date:
                start_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            if not end_date:
                end_date = start_date + timedelta(days=30)
            
            # Use sync token if provided
            if delta_link:
                # Try to use the sync token for incremental sync
                try:
                    changes = await asyncio.to_thread(
                        calendar.sync_from_token,
                        sync_token=delta_link
                    )
                    
                    # Get new and modified events
                    event_objects = []
                    for href, item in changes.items():
                        if item is not None:  # Not deleted
                            event_objects.append(item)
                    
                except Exception as sync_error:
                    logger.warning(f"Error using sync token, falling back to full sync: {sync_error}")
                    # Fall back to regular date search
                    event_objects = await asyncio.to_thread(
                        calendar.date_search,
                        start=start_date,
                        end=end_date,
                        expand=True  # Expand recurring events
                    )
            else:
                # Regular date search
                event_objects = await asyncio.to_thread(
                    calendar.date_search,
                    start=start_date,
                    end=end_date,
                    expand=True  # Expand recurring events
                )
            
            # Convert to normalized events
            events = []
            for event_obj in event_objects[:max_results]:
                # Get the iCalendar data
                ical_data = await asyncio.to_thread(lambda: event_obj.icalendar_component)
                
                # Extract event data
                try:
                    # Basic event properties
                    vevent = ical_data.subcomponents[0] if hasattr(ical_data, 'subcomponents') else ical_data
                    
                    # Start and end times
                    start_val = getattr(vevent, 'dtstart', None)
                    end_val = getattr(vevent, 'dtend', None)
                    
                    start_time = start_val.dt if start_val else None
                    end_time = end_val.dt if end_val else None
                    
                    # Check if all-day event
                    all_day = not isinstance(start_time, datetime) if start_time else False
                    
                    # Convert date to datetime for consistent handling
                    if all_day and start_time:
                        start_time = datetime.combine(start_time, datetime.min.time())
                    if all_day and end_time:
                        end_time = datetime.combine(end_time, datetime.min.time())
                    
                    # Create normalized event
                    event = CalendarEvent(
                        id=f"apple_{event_obj.id}",
                        provider=CalendarProvider.APPLE.value,
                        provider_id=event_obj.id,
                        title=str(getattr(vevent, 'summary', '')),
                        description=str(getattr(vevent, 'description', '')),
                        location=str(getattr(vevent, 'location', '')),
                        start_time=start_time.isoformat() if start_time else None,
                        end_time=end_time.isoformat() if end_time else None,
                        all_day=all_day,
                        organizer={
                            "email": str(getattr(vevent, 'organizer', '')),
                            "name": None
                        },
                        participants=[],
                        recurring=bool(getattr(vevent, 'rrule', False)),
                        calendar_id=calendar_id,
                        calendar_name=getattr(calendar, 'name', calendar_id),
                        status="confirmed",  # Default status
                        created_at=None,
                        updated_at=getattr(vevent, 'last_modified', None).dt.isoformat() if hasattr(vevent, 'last_modified') else None
                    )
                    events.append(event)
                    
                except Exception as parse_error:
                    logger.error(f"Error parsing event {event_obj.id}: {parse_error}")
                    continue
            
            # Get the current sync token for the next sync
            current_sync_token = None
            try:
                current_sync_token = await asyncio.to_thread(lambda: calendar.sync_token)
            except Exception as token_error:
                logger.warning(f"Could not get sync token: {token_error}")
            
            return {
                "events": events,
                "deltaLink": current_sync_token
            }
            
        except Exception as e:
            logger.error(f"Error getting events from Apple Calendar: {e}")
            raise
    
    async def create_event(
        self,
        token_info: Dict[str, Any],
        calendar_id: str,
        event: Dict[str, Any]
    ) -> str:
        """Create a new event in Apple Calendar"""
        try:
            # Connect to CalDAV server
            client = await self.connect(token_info)
            
            # Get principal (user)
            principal = await asyncio.to_thread(client.principal)
            
            # Find the calendar by ID
            calendar = None
            calendars = await asyncio.to_thread(principal.calendars)
            for cal in calendars:
                if cal.id == calendar_id:
                    calendar = cal
                    break
            
            if not calendar:
                raise ValueError(f"Calendar with ID {calendar_id} not found")
            
            # Create iCalendar data
            from icalendar import Calendar as iCalendar, Event as iEvent
            
            cal = iCalendar()
            cal.add('prodid', '-//Apple Calendar Service//EN')
            cal.add('version', '2.0')
            
            event_component = iEvent()
            event_component.add('summary', event.get('title', 'Untitled Event'))
            
            if event.get('description'):
                event_component.add('description', event['description'])
                
            if event.get('location'):
                event_component.add('location', event['location'])
            
            # Handle start and end times
            start_time = datetime.fromisoformat(event['start_time']) if event.get('start_time') else datetime.utcnow()
            end_time = datetime.fromisoformat(event['end_time']) if event.get('end_time') else (start_time + timedelta(hours=1))
            
            if event.get('all_day', False):
                # All-day events need date values, not datetime
                event_component.add('dtstart', start_time.date())
                event_component.add('dtend', end_time.date())
            else:
                event_component.add('dtstart', start_time)
                event_component.add('dtend', end_time)
            
            # Add UID for tracking
            event_component.add('uid', str(uuid.uuid4()))
            
            # Add to calendar
            cal.add_component(event_component)
            
            # Create the event
            ical_data = cal.to_ical()
            event_obj = await asyncio.to_thread(
                calendar.save_event,
                ical_data
            )
            
            return event_obj.id
            
        except Exception as e:
            logger.error(f"Error creating event in Apple Calendar: {e}")
            raise
            
    async def update_event(
        self,
        token_info: Dict[str, Any],
        calendar_id: str,
        event_id: str,
        event: Dict[str, Any]
    ) -> bool:
        """Update an existing event in Apple Calendar"""
        try:
            # Connect to CalDAV server
            client = await self.connect(token_info)
            
            # Get principal (user)
            principal = await asyncio.to_thread(client.principal)
            
            # Find the calendar by ID
            calendar = None
            calendars = await asyncio.to_thread(principal.calendars)
            for cal in calendars:
                if cal.id == calendar_id:
                    calendar = cal
                    break
            
            if not calendar:
                raise ValueError(f"Calendar with ID {calendar_id} not found")
            
            # Find the event
            events = await asyncio.to_thread(calendar.events)
            target_event = None
            
            for ev in events:
                if ev.id == event_id or ev.id == event_id.replace("apple_", ""):
                    target_event = ev
                    break
            
            if not target_event:
                raise ValueError(f"Event with ID {event_id} not found")
            
            # Get current event data
            ical_data = await asyncio.to_thread(lambda: target_event.icalendar_component)
            
            # Update the event
            vevent = ical_data.subcomponents[0] if hasattr(ical_data, 'subcomponents') else ical_data
            
            # Update properties
            if event.get('title'):
                vevent['summary'] = event['title']
                
            if event.get('description') is not None:
                vevent['description'] = event['description']
                
            if event.get('location') is not None:
                vevent['location'] = event['location']
            
            # Handle start and end times
            if event.get('start_time'):
                start_time = datetime.fromisoformat(event['start_time'])
                if event.get('all_day', False):
                    vevent['dtstart'] = start_time.date()
                else:
                    vevent['dtstart'] = start_time
            
            if event.get('end_time'):
                end_time = datetime.fromisoformat(event['end_time'])
                if event.get('all_day', False):
                    vevent['dtend'] = end_time.date()
                else:
                    vevent['dtend'] = end_time
            
            # Save the updated event
            await asyncio.to_thread(
                target_event.save,
                ical_data.to_ical()
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating event in Apple Calendar: {e}")
            raise
            
    async def delete_event(
        self,
        token_info: Dict[str, Any],
        calendar_id: str,
        event_id: str
    ) -> bool:
        """Delete an event from Apple Calendar"""
        try:
            # Connect to CalDAV server
            client = await self.connect(token_info)
            
            # Get principal (user)
            principal = await asyncio.to_thread(client.principal)
            
            # Find the calendar by ID
            calendar = None
            calendars = await asyncio.to_thread(principal.calendars)
            for cal in calendars:
                if cal.id == calendar_id:
                    calendar = cal
                    break
            
            if not calendar:
                raise ValueError(f"Calendar with ID {calendar_id} not found")
            
            # Find the event
            events = await asyncio.to_thread(calendar.events)
            target_event = None
            
            for ev in events:
                if ev.id == event_id or ev.id == event_id.replace("apple_", ""):
                    target_event = ev
                    break
            
            if not target_event:
                raise ValueError(f"Event with ID {event_id} not found")
            
            # Delete the event
            await asyncio.to_thread(target_event.delete)
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting event from Apple Calendar: {e}")
            raise
"""
Enhanced Exchange Web Services (EWS) calendar integration
Provides direct access to Exchange calendars using the EWS protocol
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

try:
    from exchangelib import Credentials, Account, Configuration, DELEGATE, EWSDateTime, EWSTimeZone, CalendarItem
    from exchangelib.errors import EWSError
    EWS_AVAILABLE = True
except ImportError:
    EWS_AVAILABLE = False
    CalendarItem = None

from services.calendar_event import CalendarEvent, CalendarProvider

logger = logging.getLogger(__name__)

@dataclass
class ExchangeConfig:
    """Exchange server configuration"""
    server_url: str
    username: str
    password: str
    email: str
    version: Optional[str] = None  # e.g., 'Exchange2016'
    auth_type: str = "basic"  # basic, ntlm, digest
    verify_ssl: bool = True

class ExchangeCalendarService:
    """Enhanced Exchange Web Services calendar integration"""
    
    def __init__(self, config: ExchangeConfig):
        """Initialize the Exchange calendar service"""
        if not EWS_AVAILABLE:
            raise ImportError(
                "exchangelib is not installed. Install it with: pip install exchangelib"
            )
        
        self.config = config
        self.account = None
        self.provider = CalendarProvider.EXCHANGE
        
        # Initialize connection
        self._connect()
    
    def _connect(self):
        """Establish connection to Exchange server"""
        try:
            # Create credentials
            credentials = Credentials(
                username=self.config.username,
                password=self.config.password
            )
            
            # Create configuration
            if self.config.server_url.startswith('https://'):
                server = self.config.server_url
            else:
                server = f"https://{self.config.server_url}"
            
            # Try autodiscovery first, then fall back to manual configuration
            try:
                self.account = Account(
                    primary_smtp_address=self.config.email,
                    credentials=credentials,
                    autodiscover=True,
                    access_type=DELEGATE
                )
                logger.info("Connected to Exchange using autodiscovery")
            except Exception as autodiscover_error:
                logger.warning(f"Autodiscovery failed: {autodiscover_error}, trying manual configuration")
                
                config = Configuration(
                    server=server,
                    credentials=credentials,
                    auth_type=self.config.auth_type,
                    version=None,  # Let exchangelib detect version
                    retry_policy=None
                )
                
                self.account = Account(
                    primary_smtp_address=self.config.email,
                    config=config,
                    autodiscover=False,
                    access_type=DELEGATE
                )
                logger.info("Connected to Exchange using manual configuration")
                
        except Exception as e:
            logger.error(f"Failed to connect to Exchange server: {e}")
            raise
    
    def test_connection(self) -> bool:
        """Test the Exchange connection"""
        try:
            if not self.account:
                return False
            
            # Try to access the calendar folder
            calendar = self.account.calendar
            # Simple test query
            items = list(calendar.filter(
                start__gte=EWSDateTime.now() - timedelta(days=1),
                end__lte=EWSDateTime.now()
            )[:1])
            
            logger.info("Exchange connection test successful")
            return True
            
        except Exception as e:
            logger.error(f"Exchange connection test failed: {e}")
            return False
    
    async def list_calendars(self) -> List[Dict[str, Any]]:
        """List available Exchange calendars"""
        try:
            if not self.account:
                logger.error("Not connected to Exchange server")
                return []
            
            calendars = []
            
            # Primary calendar
            calendars.append({
                'id': 'primary',
                'name': f"{self.config.email} Calendar",
                'summary': f"Primary calendar for {self.config.email}",
                'description': f"Exchange calendar for {self.config.email}",
                'primary': True,
                'writable': True,
                'provider': 'exchange',
                'email': self.config.email
            })
            
            # Try to find additional calendars (shared, delegated, etc.)
            try:
                # This is a simplified approach - in production you might want to
                # enumerate all calendar folders
                from exchangelib import Folder
                
                # Look for additional calendar folders
                additional_calendars = self.account.root.glob('**/Calendar*')
                for i, folder in enumerate(additional_calendars):
                    if folder != self.account.calendar:
                        calendars.append({
                            'id': f'calendar_{i}',
                            'name': folder.name,
                            'summary': f"Additional calendar: {folder.name}",
                            'description': f"Exchange calendar folder: {folder.name}",
                            'primary': False,
                            'writable': True,
                            'provider': 'exchange',
                            'email': self.config.email,
                            'folder_id': folder.folder_id
                        })
            except Exception as e:
                logger.debug(f"Could not enumerate additional calendars: {e}")
            
            return calendars
            
        except Exception as e:
            logger.error(f"Error listing Exchange calendars: {e}")
            return []
    
    async def get_events(
        self,
        calendar_id: str = 'primary',
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        max_results: int = 100
    ) -> List[CalendarEvent]:
        """Get events from Exchange calendar"""
        try:
            if not self.account:
                logger.error("Not connected to Exchange server")
                return []
            
            # Set default date range
            if not start_date:
                start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            if not end_date:
                end_date = start_date + timedelta(days=30)
            
            # Convert to EWS datetime (timezone aware)
            tz = EWSTimeZone.localzone()
            ews_start = tz.localize(EWSDateTime.from_datetime(start_date))
            ews_end = tz.localize(EWSDateTime.from_datetime(end_date))
            
            # Get the calendar folder
            if calendar_id == 'primary':
                calendar = self.account.calendar
            else:
                # For additional calendars, you'd need to implement folder lookup
                calendar = self.account.calendar
            
            # Query for calendar items
            items = calendar.filter(
                start__gte=ews_start,
                end__lte=ews_end
            ).order_by('start')[:max_results]
            
            events = []
            for item in items:
                try:
                    event = self._convert_exchange_item_to_calendar_event(item, calendar_id)
                    if event:
                        events.append(event)
                except Exception as e:
                    logger.error(f"Error converting Exchange item to CalendarEvent: {e}")
                    continue
            
            logger.info(f"Retrieved {len(events)} events from Exchange calendar")
            return events
            
        except Exception as e:
            logger.error(f"Error getting events from Exchange: {e}")
            return []
    
    def _convert_exchange_item_to_calendar_event(self, item: CalendarItem, calendar_id: str) -> Optional[CalendarEvent]:
        """Convert an Exchange calendar item to a CalendarEvent"""
        try:
            # Extract basic information
            event_id = str(item.item_id) if hasattr(item, 'item_id') else str(item.id)
            title = item.subject or "Untitled Event"
            description = ""
            if hasattr(item, 'body') and item.body:
                description = str(item.body)[:1000]  # Limit description length
            
            # Handle start and end times
            start_time = item.start.astimezone() if item.start else datetime.now()
            end_time = item.end.astimezone() if item.end else start_time + timedelta(hours=1)
            
            # Check if all day event
            all_day = getattr(item, 'is_all_day', False)
            if all_day and isinstance(start_time, datetime):
                # For all-day events, normalize to date only
                start_time = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
                end_time = end_time.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            # Extract location
            location = getattr(item, 'location', '') or ''
            
            # Extract organizer information
            organizer = {}
            if hasattr(item, 'organizer') and item.organizer:
                organizer = {
                    'email': getattr(item.organizer, 'email_address', ''),
                    'name': getattr(item.organizer, 'name', '')
                }
            
            # Extract attendees/participants
            participants = []
            if hasattr(item, 'required_attendees') and item.required_attendees:
                for attendee in item.required_attendees:
                    if hasattr(attendee, 'email_address'):
                        participants.append({
                            'email': attendee.email_address,
                            'name': getattr(attendee, 'name', attendee.email_address),
                            'status': 'accepted'  # Default status
                        })
            
            # Check for recurrence
            recurring = hasattr(item, 'recurrence') and item.recurrence is not None
            
            # Extract privacy/sensitivity
            private = getattr(item, 'sensitivity', '').lower() in ['private', 'confidential']
            
            # Create CalendarEvent
            event = CalendarEvent(
                id=event_id,
                provider_id=event_id,
                title=title,
                description=description,
                start_time=start_time,
                end_time=end_time,
                all_day=all_day,
                calendar_id=calendar_id,
                calendar_name="Exchange Calendar",
                location=location,
                organizer=organizer,
                participants=participants,
                recurring=recurring,
                private=private,
                provider=self.provider,
                created_at=getattr(item, 'datetime_created', datetime.now()),
                modified_at=getattr(item, 'last_modified_time', datetime.now())
            )
            
            return event
            
        except Exception as e:
            logger.error(f"Error converting Exchange calendar item: {e}")
            return None
    
    async def create_event(self, event_data: Dict[str, Any], calendar_id: str = 'primary') -> Optional[str]:
        """Create a new event in Exchange calendar"""
        try:
            if not self.account:
                logger.error("Not connected to Exchange server")
                return None
            
            # Get the calendar folder
            calendar = self.account.calendar
            
            # Convert datetime strings to EWS datetime objects
            tz = EWSTimeZone.localzone()
            
            start_time = event_data.get('start_time')
            end_time = event_data.get('end_time')
            
            if isinstance(start_time, str):
                start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            if isinstance(end_time, str):
                end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            
            # Create calendar item
            item = CalendarItem(
                account=self.account,
                folder=calendar,
                subject=event_data.get('title', 'Untitled Event'),
                body=event_data.get('description', ''),
                start=tz.localize(EWSDateTime.from_datetime(start_time)),
                end=tz.localize(EWSDateTime.from_datetime(end_time)),
                location=event_data.get('location', ''),
                is_all_day=event_data.get('all_day', False)
            )
            
            # Add attendees if specified
            attendees = event_data.get('participants', [])
            if attendees:
                from exchangelib import Attendee, Mailbox
                item.required_attendees = [
                    Attendee(mailbox=Mailbox(email_address=attendee['email']))
                    for attendee in attendees
                    if attendee.get('email')
                ]
            
            # Save the item
            item.save()
            
            logger.info(f"Created Exchange event: {item.subject}")
            return str(item.item_id) if hasattr(item, 'item_id') else str(item.id)
            
        except Exception as e:
            logger.error(f"Error creating Exchange event: {e}")
            return None
    
    async def update_event(self, event_id: str, event_data: Dict[str, Any], calendar_id: str = 'primary') -> bool:
        """Update an existing event in Exchange calendar"""
        try:
            if not self.account:
                logger.error("Not connected to Exchange server")
                return False
            
            # Find the event by ID
            calendar = self.account.calendar
            items = list(calendar.filter(item_id=event_id))
            
            if not items:
                logger.error(f"Event not found: {event_id}")
                return False
            
            item = items[0]
            
            # Update fields
            if 'title' in event_data:
                item.subject = event_data['title']
            if 'description' in event_data:
                item.body = event_data['description']
            if 'location' in event_data:
                item.location = event_data['location']
            if 'start_time' in event_data:
                start_time = event_data['start_time']
                if isinstance(start_time, str):
                    start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                tz = EWSTimeZone.localzone()
                item.start = tz.localize(EWSDateTime.from_datetime(start_time))
            if 'end_time' in event_data:
                end_time = event_data['end_time']
                if isinstance(end_time, str):
                    end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                tz = EWSTimeZone.localzone()
                item.end = tz.localize(EWSDateTime.from_datetime(end_time))
            
            # Save changes
            item.save(update_fields=['subject', 'body', 'location', 'start', 'end'])
            
            logger.info(f"Updated Exchange event: {event_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating Exchange event: {e}")
            return False
    
    async def delete_event(self, event_id: str, calendar_id: str = 'primary') -> bool:
        """Delete an event from Exchange calendar"""
        try:
            if not self.account:
                logger.error("Not connected to Exchange server")
                return False
            
            # Find the event by ID
            calendar = self.account.calendar
            items = list(calendar.filter(item_id=event_id))
            
            if not items:
                logger.error(f"Event not found: {event_id}")
                return False
            
            item = items[0]
            item.delete()
            
            logger.info(f"Deleted Exchange event: {event_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting Exchange event: {e}")
            return False
    
    @classmethod
    def is_available(cls) -> bool:
        """Check if EWS integration is available"""
        return EWS_AVAILABLE
    
    def get_server_info(self) -> Dict[str, Any]:
        """Get Exchange server information"""
        try:
            if not self.account or not self.account.protocol:
                return {}
            
            protocol = self.account.protocol
            return {
                'server': getattr(protocol, 'server', 'Unknown'),
                'version': str(getattr(protocol, 'version', 'Unknown')),
                'service_endpoint': str(getattr(protocol, 'service_endpoint', 'Unknown')),
                'auth_type': getattr(protocol, 'auth_type', 'Unknown')
            }
        except Exception as e:
            logger.error(f"Error getting server info: {e}")
            return {}
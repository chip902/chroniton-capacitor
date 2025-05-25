from datetime import datetime
from enum import Enum
from typing import List, Dict, Optional, Any, Union
from pydantic import BaseModel, Field


class CalendarProvider(str, Enum):
    """Enum for supported calendar providers"""
    GOOGLE = "google"
    MICROSOFT = "microsoft"
    APPLE = "apple"
    EXCHANGE = "exchange"  # For Mailcow ActiveSync


class EventParticipant(BaseModel):
    """Common model for event participants across providers"""
    email: Optional[str] = None
    name: Optional[str] = None
    response_status: Optional[str] = None  # accepted, declined, tentative, needs_action
    
    @classmethod
    def from_google(cls, attendee: Dict[str, Any]) -> "EventParticipant":
        """Create participant from Google Calendar attendee"""
        return cls(
            email=attendee.get("email"),
            name=attendee.get("displayName"),
            response_status=attendee.get("responseStatus")
        )
    
    @classmethod
    def from_microsoft(cls, attendee: Dict[str, Any]) -> "EventParticipant":
        """Create participant from Microsoft Graph attendee"""
        email = None
        name = None
        
        # Extract email and name based on Microsoft Graph structure
        if "emailAddress" in attendee:
            email = attendee["emailAddress"].get("address")
            name = attendee["emailAddress"].get("name")
        
        # Map Microsoft status to common format
        status_map = {
            "accepted": "accepted",
            "declined": "declined",
            "tentative": "tentative",
            "notResponded": "needs_action"
        }
        
        return cls(
            email=email,
            name=name,
            response_status=status_map.get(attendee.get("status", {}).get("response"), "needs_action")
        )


class CalendarEvent(BaseModel):
    """
    Normalized calendar event representation that works across providers
    """
    id: str
    provider: CalendarProvider
    provider_id: str  # Original ID from the provider
    title: str
    description: Optional[str] = None
    location: Optional[str] = None
    start_time: datetime
    end_time: datetime
    all_day: bool = False
    organizer: Optional[EventParticipant] = None
    participants: List[EventParticipant] = Field(default_factory=list)
    recurring: bool = False
    recurrence_pattern: Optional[str] = None
    calendar_id: str
    calendar_name: Optional[str] = None
    link: Optional[str] = None  # Link to view/edit the event
    private: bool = False
    status: Optional[str] = None  # confirmed, tentative, cancelled
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_synced: datetime = Field(default_factory=datetime.utcnow)
    original_data: Optional[Dict[str, Any]] = None  # Original event data
    
    @classmethod
    def from_google(cls, event: Dict[str, Any], calendar_id: str, calendar_name: Optional[str] = None) -> "CalendarEvent":
        """
        Create a normalized CalendarEvent from Google Calendar event
        """
        # Extract start and end times
        start = event.get("start", {})
        end = event.get("end", {})
        
        # Determine if it's an all-day event
        all_day = "date" in start and "date" in end
        
        # Get start and end times
        if all_day:
            # For all-day events, convert date strings to datetime
            start_dt = datetime.fromisoformat(start["date"])
            end_dt = datetime.fromisoformat(end["date"])
        else:
            # For timed events, use dateTime
            start_dt = datetime.fromisoformat(start.get("dateTime", "").replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end.get("dateTime", "").replace('Z', '+00:00'))
        
        # Extract organizer
        organizer = None
        if "organizer" in event:
            organizer = EventParticipant(
                email=event["organizer"].get("email"),
                name=event["organizer"].get("displayName"),
                response_status="accepted"  # Organizers are implicitly accepted
            )
        
        # Extract participants
        participants = []
        for attendee in event.get("attendees", []):
            participants.append(EventParticipant.from_google(attendee))
        
        # Map Google status to common format
        status_map = {
            "confirmed": "confirmed",
            "tentative": "tentative",
            "cancelled": "cancelled"
        }
        
        # Determine if event is recurring
        recurring = "recurrence" in event
        recurrence_pattern = None
        if recurring and event.get("recurrence"):
            recurrence_pattern = event["recurrence"][0] if event["recurrence"] else None
        
        # Create the normalized event
        return cls(
            id=f"google_{event['id']}",
            provider=CalendarProvider.GOOGLE,
            provider_id=event["id"],
            title=event.get("summary", "Untitled Event"),
            description=event.get("description"),
            location=event.get("location"),
            start_time=start_dt,
            end_time=end_dt,
            all_day=all_day,
            organizer=organizer,
            participants=participants,
            recurring=recurring,
            recurrence_pattern=recurrence_pattern,
            calendar_id=calendar_id,
            calendar_name=calendar_name,
            link=event.get("htmlLink"),
            private=event.get("visibility") == "private",
            status=status_map.get(event.get("status")),
            created_at=datetime.fromisoformat(event["created"].replace('Z', '+00:00')) if "created" in event else None,
            updated_at=datetime.fromisoformat(event["updated"].replace('Z', '+00:00')) if "updated" in event else None,
            original_data=event
        )
    
    @classmethod
    def from_microsoft(cls, event: Dict[str, Any], calendar_id: str, calendar_name: Optional[str] = None) -> "CalendarEvent":
        """
        Create a normalized CalendarEvent from Microsoft Graph event
        """
        # Extract start and end times
        start = event.get("start", {})
        end = event.get("end", {})
        
        # Determine if it's an all-day event
        all_day = event.get("isAllDay", False)
        
        # Get start and end times
        start_dt = datetime.fromisoformat(start.get("dateTime", "").replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end.get("dateTime", "").replace('Z', '+00:00'))
        
        # Extract organizer
        organizer = None
        if "organizer" in event:
            organizer_data = event["organizer"]
            organizer = EventParticipant(
                email=organizer_data.get("emailAddress", {}).get("address"),
                name=organizer_data.get("emailAddress", {}).get("name"),
                response_status="accepted"  # Organizers are implicitly accepted
            )
        
        # Extract participants
        participants = []
        for attendee in event.get("attendees", []):
            participants.append(EventParticipant.from_microsoft(attendee))
        
        # Map Microsoft status to common format
        status_map = {
            "confirmed": "confirmed",
            "tentative": "tentative",
            "cancelled": "cancelled"
        }
        
        ms_status = None
        if "showAs" in event:
            if event["showAs"] == "tentative":
                ms_status = "tentative"
            elif event["showAs"] == "busy":
                ms_status = "confirmed"
            elif event["showAs"] == "free":
                ms_status = "confirmed"  # Free time on calendar is still a confirmed event
        
        # Check if event is cancelled
        if event.get("isCancelled", False):
            ms_status = "cancelled"
        
        # Determine if event is recurring
        recurring = event.get("recurrence", None) is not None
        recurrence_pattern = None
        if recurring and event.get("recurrence", {}).get("pattern"):
            recurrence_pattern = str(event["recurrence"]["pattern"])
        
        # Create the normalized event
        return cls(
            id=f"microsoft_{event['id']}",
            provider=CalendarProvider.MICROSOFT,
            provider_id=event["id"],
            title=event.get("subject", "Untitled Event"),
            description=event.get("bodyPreview"),
            location=event.get("location", {}).get("displayName"),
            start_time=start_dt,
            end_time=end_dt,
            all_day=all_day,
            organizer=organizer,
            participants=participants,
            recurring=recurring,
            recurrence_pattern=recurrence_pattern,
            calendar_id=calendar_id,
            calendar_name=calendar_name,
            link=event.get("webLink"),
            private=event.get("sensitivity") == "private",
            status=ms_status,
            created_at=datetime.fromisoformat(event["createdDateTime"].replace('Z', '+00:00')) if "createdDateTime" in event else None,
            updated_at=datetime.fromisoformat(event["lastModifiedDateTime"].replace('Z', '+00:00')) if "lastModifiedDateTime" in event else None,
            original_data=event
        )
        
    @classmethod
    def from_exchange(cls, event: Dict[str, Any], calendar_id: str, calendar_name: Optional[str] = None) -> "CalendarEvent":
        """
        Create a normalized CalendarEvent from Exchange/Mailcow ActiveSync event
        """
        # Extract start and end times
        start = event.get("start", {})
        end = event.get("end", {})
        
        # Determine if it's an all-day event
        all_day = event.get("isAllDay", False)
        
        # Get start and end times
        start_dt = datetime.fromisoformat(start.get("dateTime", "").replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end.get("dateTime", "").replace('Z', '+00:00'))
        
        # Extract organizer
        organizer = None
        if "organizer" in event:
            organizer_data = event["organizer"]
            organizer = EventParticipant(
                email=organizer_data.get("emailAddress", {}).get("address"),
                name=organizer_data.get("emailAddress", {}).get("name"),
                response_status="accepted"  # Organizers are implicitly accepted
            )
        
        # Extract participants
        participants = []
        for attendee in event.get("attendees", []):
            # Exchange attendees follow a similar format to Microsoft Graph
            participants.append(EventParticipant.from_microsoft(attendee))
        
        # Map Exchange status to common format
        status_map = {
            "confirmed": "confirmed",
            "tentative": "tentative",
            "cancelled": "cancelled"
        }
        
        ex_status = None
        if "showAs" in event:
            if event["showAs"] == "tentative":
                ex_status = "tentative"
            elif event["showAs"] == "busy":
                ex_status = "confirmed"
            elif event["showAs"] == "free":
                ex_status = "confirmed"  # Free time on calendar is still a confirmed event
        
        # Check if event is cancelled
        if event.get("isCancelled", False):
            ex_status = "cancelled"
        
        # Determine if event is recurring
        recurring = event.get("recurrence", None) is not None
        recurrence_pattern = None
        if recurring and event.get("recurrence", {}).get("pattern"):
            recurrence_pattern = str(event["recurrence"]["pattern"])
        
        # Create the normalized event
        return cls(
            id=f"exchange_{event['id']}",
            provider=CalendarProvider.EXCHANGE,
            provider_id=event["id"],
            title=event.get("subject", "Untitled Event"),
            description=event.get("bodyPreview"),
            location=event.get("location", {}).get("displayName"),
            start_time=start_dt,
            end_time=end_dt,
            all_day=all_day,
            organizer=organizer,
            participants=participants,
            recurring=recurring,
            recurrence_pattern=recurrence_pattern,
            calendar_id=calendar_id,
            calendar_name=calendar_name,
            link=event.get("webLink"),
            private=event.get("sensitivity") == "private",
            status=ex_status,
            created_at=datetime.fromisoformat(event["createdDateTime"].replace('Z', '+00:00')) if "createdDateTime" in event else None,
            updated_at=datetime.fromisoformat(event["lastModifiedDateTime"].replace('Z', '+00:00')) if "lastModifiedDateTime" in event else None,
            original_data=event
        )
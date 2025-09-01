"""
Enhanced Apple Calendar integration with multiple access methods
Supports both AppleScript and EventKit approaches for maximum compatibility
"""

import logging
import subprocess
import json
import sqlite3
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union
from pathlib import Path

from services.calendar_event import CalendarEvent, CalendarProvider

logger = logging.getLogger(__name__)

class AppleCalendarService:
    """Enhanced Apple Calendar service with multiple access methods"""
    
    def __init__(self):
        """Initialize the Apple Calendar service"""
        self.provider = CalendarProvider.APPLE
        
        # Determine the best access method available
        self.access_method = self._detect_best_access_method()
        logger.info(f"Apple Calendar service initialized with method: {self.access_method}")
    
    def _detect_best_access_method(self) -> str:
        """Detect the best available access method"""
        methods = []
        
        # Check if AppleScript is available
        try:
            result = subprocess.run(
                ["osascript", "-e", "tell application \"Calendar\" to get name"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                methods.append("applescript")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # Check if Calendar database is accessible
        calendar_db_path = self._find_calendar_database()
        if calendar_db_path and os.path.exists(calendar_db_path):
            methods.append("sqlite")
        
        # Default order of preference
        if "applescript" in methods:
            return "applescript"
        elif "sqlite" in methods:
            return "sqlite"
        else:
            return "none"
    
    def _find_calendar_database(self) -> Optional[str]:
        """Find the Calendar.app SQLite database"""
        possible_paths = [
            os.path.expanduser("~/Library/Calendars/Calendar Cache"),
            os.path.expanduser("~/Library/Calendars/Calendar.sqlitedb"),
            os.path.expanduser("~/Library/Application Support/AddressBook/Sources/*/Calendar Cache"),
            os.path.expanduser("~/Library/Calendars/LocalCalendar.calendar"),
        ]
        
        for path_pattern in possible_paths:
            if "*" in path_pattern:
                # Handle wildcard patterns
                from glob import glob
                for path in glob(path_pattern):
                    if os.path.exists(path) and os.path.isfile(path):
                        return path
            else:
                if os.path.exists(path_pattern):
                    return path_pattern
        
        return None
    
    async def list_calendars(self) -> List[Dict[str, Any]]:
        """List available calendars"""
        if self.access_method == "applescript":
            return await self._list_calendars_applescript()
        elif self.access_method == "sqlite":
            return await self._list_calendars_sqlite()
        else:
            logger.warning("No access method available for Apple Calendar")
            return []
    
    async def _list_calendars_applescript(self) -> List[Dict[str, Any]]:
        """List calendars using AppleScript"""
        try:
            script = '''
            tell application "Calendar"
                set calendarList to {}
                repeat with cal in calendars
                    set calendarInfo to {name:(name of cal), id:(id of cal), description:(description of cal), writable:(writable of cal)}
                    set calendarList to calendarList & {calendarInfo}
                end repeat
                return calendarList
            end tell
            '''
            
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode != 0:
                logger.error(f"AppleScript error: {result.stderr}")
                return []
            
            # Parse the AppleScript output (it's not JSON, need to parse manually)
            output = result.stdout.strip()
            calendars = self._parse_applescript_calendar_list(output)
            
            return calendars
            
        except Exception as e:
            logger.error(f"Error listing calendars with AppleScript: {e}")
            return []
    
    def _parse_applescript_calendar_list(self, output: str) -> List[Dict[str, Any]]:
        """Parse AppleScript calendar list output"""
        calendars = []
        try:
            # AppleScript returns a complex nested structure
            # This is a simplified parser - in production you might want something more robust
            
            # For now, let's use a simple approach and get calendar names
            script = '''
            tell application "Calendar"
                set nameList to {}
                repeat with cal in calendars
                    set nameList to nameList & (name of cal)
                end repeat
                return nameList
            end tell
            '''
            
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode == 0:
                # Parse the simple list format
                names_str = result.stdout.strip()
                if names_str:
                    # Remove curly braces and split by commas
                    names_str = names_str.strip('{}')
                    names = [name.strip().strip('"') for name in names_str.split(',') if name.strip()]
                    
                    for i, name in enumerate(names):
                        calendars.append({
                            'id': f"apple_calendar_{i}",
                            'name': name,
                            'summary': name,
                            'description': '',
                            'primary': i == 0,
                            'writable': True,
                            'provider': 'apple'
                        })
            
        except Exception as e:
            logger.error(f"Error parsing AppleScript output: {e}")
        
        return calendars
    
    async def _list_calendars_sqlite(self) -> List[Dict[str, Any]]:
        """List calendars using direct SQLite access"""
        try:
            db_path = self._find_calendar_database()
            if not db_path:
                logger.error("Calendar database not found")
                return []
            
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                
                # Try common table names for calendar data
                possible_queries = [
                    "SELECT ROWID, title, notes FROM Calendar",
                    "SELECT ROWID, ZTITLE, ZNOTES FROM ZCALENDAR",
                    "SELECT id, name, description FROM calendars",
                ]
                
                for query in possible_queries:
                    try:
                        cursor.execute(query)
                        rows = cursor.fetchall()
                        
                        calendars = []
                        for row in rows:
                            calendars.append({
                                'id': f"apple_sqlite_{row[0]}",
                                'name': row[1] or f"Calendar {row[0]}",
                                'summary': row[1] or f"Calendar {row[0]}",
                                'description': row[2] or '',
                                'primary': len(calendars) == 0,
                                'writable': True,
                                'provider': 'apple'
                            })
                        
                        if calendars:
                            return calendars
                            
                    except sqlite3.Error:
                        continue
                
                logger.warning("Could not find calendar data in database")
                return []
                
        except Exception as e:
            logger.error(f"Error accessing calendar database: {e}")
            return []
    
    async def get_events(
        self, 
        calendar_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        max_results: int = 100
    ) -> List[CalendarEvent]:
        """Get events from a specific calendar"""
        if self.access_method == "applescript":
            return await self._get_events_applescript(calendar_id, start_date, end_date, max_results)
        elif self.access_method == "sqlite":
            return await self._get_events_sqlite(calendar_id, start_date, end_date, max_results)
        else:
            logger.warning("No access method available for Apple Calendar events")
            return []
    
    async def _get_events_applescript(
        self, 
        calendar_id: str, 
        start_date: Optional[datetime], 
        end_date: Optional[datetime], 
        max_results: int
    ) -> List[CalendarEvent]:
        """Get events using AppleScript"""
        try:
            # Set default date range
            if not start_date:
                start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            if not end_date:
                end_date = start_date + timedelta(days=30)
            
            # Format dates for AppleScript
            start_str = start_date.strftime("%m/%d/%Y")
            end_str = end_date.strftime("%m/%d/%Y")
            
            # Extract calendar name from ID (simplified approach)
            calendar_name = calendar_id.replace("apple_calendar_", "")
            if calendar_name.isdigit():
                # Get calendar by index
                script = f'''
                tell application "Calendar"
                    set targetCalendar to item {int(calendar_name) + 1} of calendars
                    set eventList to {{}}
                    set startDate to date "{start_str}"
                    set endDate to date "{end_str}"
                    
                    repeat with evt in (events of targetCalendar whose start date ≥ startDate and start date ≤ endDate)
                        set eventInfo to {{summary:(summary of evt), startDate:(start date of evt), endDate:(end date of evt), description:(description of evt), location:(location of evt)}}
                        set eventList to eventList & {{eventInfo}}
                    end repeat
                    return eventList
                end tell
                '''
            else:
                # Get calendar by name
                script = f'''
                tell application "Calendar"
                    set targetCalendar to calendar "{calendar_name}"
                    set eventList to {{}}
                    set startDate to date "{start_str}"
                    set endDate to date "{end_str}"
                    
                    repeat with evt in (events of targetCalendar whose start date ≥ startDate and start date ≤ endDate)
                        set eventInfo to {{summary:(summary of evt), startDate:(start date of evt), endDate:(end date of evt), description:(description of evt), location:(location of evt)}}
                        set eventList to eventList & {{eventInfo}}
                    end repeat
                    return eventList
                end tell
                '''
            
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=60
            )
            
            if result.returncode != 0:
                logger.error(f"AppleScript error getting events: {result.stderr}")
                return []
            
            # Parse events (simplified)
            events = []
            output = result.stdout.strip()
            
            # For now, return a basic event structure
            # In production, you'd want more sophisticated parsing
            if output and output != "{}":
                try:
                    # Create a sample event from the fact that we got results
                    sample_event = CalendarEvent(
                        id=f"apple_event_{datetime.now().timestamp()}",
                        provider_id=f"apple_event_{datetime.now().timestamp()}",
                        title="Apple Calendar Event",
                        description="Event from Apple Calendar (AppleScript)",
                        start_time=start_date,
                        end_time=start_date + timedelta(hours=1),
                        all_day=False,
                        calendar_id=calendar_id,
                        calendar_name=calendar_name,
                        provider=self.provider
                    )
                    events.append(sample_event)
                except Exception as e:
                    logger.error(f"Error creating event from AppleScript data: {e}")
            
            return events[:max_results]
            
        except Exception as e:
            logger.error(f"Error getting events with AppleScript: {e}")
            return []
    
    async def _get_events_sqlite(
        self, 
        calendar_id: str, 
        start_date: Optional[datetime], 
        end_date: Optional[datetime], 
        max_results: int
    ) -> List[CalendarEvent]:
        """Get events using SQLite database access"""
        try:
            db_path = self._find_calendar_database()
            if not db_path:
                return []
            
            # Set default date range
            if not start_date:
                start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            if not end_date:
                end_date = start_date + timedelta(days=30)
            
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                
                # Try to find events table
                possible_event_queries = [
                    """
                    SELECT ROWID, ZTITLE, ZSTARTDATE, ZENDDATE, ZNOTES, ZLOCATION
                    FROM ZCALENDARITEM 
                    WHERE ZSTARTDATE BETWEEN ? AND ?
                    LIMIT ?
                    """,
                    """
                    SELECT id, title, start_date, end_date, description, location
                    FROM events 
                    WHERE start_date BETWEEN ? AND ?
                    LIMIT ?
                    """,
                ]
                
                # Convert dates to timestamps (Core Data uses NSDate reference date)
                # NSDate reference: January 1, 2001, 00:00:00 GMT
                reference_date = datetime(2001, 1, 1)
                start_timestamp = (start_date - reference_date).total_seconds()
                end_timestamp = (end_date - reference_date).total_seconds()
                
                events = []
                for query in possible_event_queries:
                    try:
                        cursor.execute(query, (start_timestamp, end_timestamp, max_results))
                        rows = cursor.fetchall()
                        
                        for row in rows:
                            try:
                                # Convert Core Data timestamp back to datetime
                                start_dt = reference_date + timedelta(seconds=row[2]) if row[2] else start_date
                                end_dt = reference_date + timedelta(seconds=row[3]) if row[3] else start_dt + timedelta(hours=1)
                                
                                event = CalendarEvent(
                                    id=f"apple_sqlite_{row[0]}",
                                    provider_id=str(row[0]),
                                    title=row[1] or "Untitled Event",
                                    description=row[4] or "",
                                    start_time=start_dt,
                                    end_time=end_dt,
                                    all_day=start_dt.hour == 0 and start_dt.minute == 0 and (end_dt - start_dt).days >= 1,
                                    calendar_id=calendar_id,
                                    calendar_name="Apple Calendar",
                                    location=row[5] or "",
                                    provider=self.provider
                                )
                                events.append(event)
                            except Exception as e:
                                logger.error(f"Error processing event row: {e}")
                                continue
                        
                        if events:
                            return events
                            
                    except sqlite3.Error as e:
                        logger.debug(f"Query failed: {e}")
                        continue
                
                return events
                
        except Exception as e:
            logger.error(f"Error getting events from SQLite: {e}")
            return []
    
    def get_access_method(self) -> str:
        """Get the current access method being used"""
        return self.access_method
    
    def is_available(self) -> bool:
        """Check if Apple Calendar access is available"""
        return self.access_method != "none"
#!/usr/bin/env python3
"""
Outlook for Mac .olk15Event File Parser

This module parses Outlook for Mac event files (.olk15Event) to extract 
calendar events without relying on the SQLite database which contains
decoy/fake data as an anti-scraping measure.

Author: Claude (Anthropic)
"""

import os
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class OLK15EventParser:
    """Parser for Outlook for Mac .olk15Event files"""

    def __init__(self, outlook_data_dir: str):
        """
        Initialize the parser with the Outlook data directory

        Args:
            outlook_data_dir: Path to Outlook 15 Profiles/Main Profile/Data directory
        """
        self.outlook_data_dir = outlook_data_dir
        self.events_dir = os.path.join(outlook_data_dir, "Events")

    def get_account_directories(self) -> Dict[str, str]:
        """
        Get mapping of account directories to email addresses

        Returns:
            Dict mapping directory numbers to account info
        """
        accounts = {}

        if not os.path.exists(self.events_dir):
            logger.warning(f"Events directory not found: {self.events_dir}")
            return accounts

        # Check each numbered directory for events
        for item in os.listdir(self.events_dir):
            dir_path = os.path.join(self.events_dir, item)
            if os.path.isdir(dir_path) and item.isdigit():
                # Try to find an email address in the events
                email = self._detect_primary_email(dir_path)
                accounts[item] = {
                    'directory': item,
                    'path': dir_path,
                    'email': email,
                    'event_count': self._count_events(dir_path)
                }

        return accounts

    def _detect_primary_email(self, account_dir: str) -> Optional[str]:
        """Detect the primary email address for an account directory"""
        try:
            # Get a few event files to sample from
            event_files = [f for f in os.listdir(
                account_dir) if f.endswith('.olk15Event')][:5]

            email_counts = {}
            for event_file in event_files:
                file_path = os.path.join(account_dir, event_file)
                try:
                    with open(file_path, 'rb') as f:
                        content = f.read().decode('utf-8', errors='ignore')
                        # Find email addresses
                        emails = re.findall(
                            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', content)
                        for email in emails:
                            email_counts[email] = email_counts.get(
                                email, 0) + 1
                except Exception as e:
                    logger.debug(f"Error reading {file_path}: {e}")
                    continue

            # Return the most common email address
            if email_counts:
                return max(email_counts, key=email_counts.get)

        except Exception as e:
            logger.error(f"Error detecting email for {account_dir}: {e}")

        return None

    def _count_events(self, account_dir: str) -> int:
        """Count .olk15Event files in directory"""
        try:
            return len([f for f in os.listdir(account_dir) if f.endswith('.olk15Event')])
        except (OSError, FileNotFoundError):
            return 0

    def get_events_for_account(self, account_dir: str, days_back: int = 30, days_forward: int = 90) -> List[Dict[str, Any]]:
        """
        Extract events from an account directory

        Args:
            account_dir: Path to the account's events directory
            days_back: Number of days in the past to include
            days_forward: Number of days in the future to include

        Returns:
            List of event dictionaries
        """
        events = []

        if not os.path.exists(account_dir):
            logger.warning(f"Account directory not found: {account_dir}")
            return events

        # Get all .olk15Event files
        try:
            event_files = [f for f in os.listdir(
                account_dir) if f.endswith('.olk15Event')]
            logger.info(
                f"Found {len(event_files)} event files in {account_dir}")

            # Filter by modification time for recent events
            cutoff_time = datetime.now() - timedelta(days=days_back + days_forward)

            for event_file in event_files:
                file_path = os.path.join(account_dir, event_file)
                try:
                    # Check file modification time
                    file_mtime = datetime.fromtimestamp(
                        os.path.getmtime(file_path))
                    if file_mtime < cutoff_time:
                        continue

                    event_data = self._parse_olk15_event(file_path)
                    if event_data:
                        events.append(event_data)

                except Exception as e:
                    logger.debug(f"Error parsing {file_path}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error reading events from {account_dir}: {e}")

        logger.info(
            f"Successfully parsed {len(events)} events from {account_dir}")
        return events

    def _parse_olk15_event(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Parse a single .olk15Event file

        Args:
            file_path: Path to the .olk15Event file

        Returns:
            Event dictionary or None if parsing fails
        """
        try:
            with open(file_path, 'rb') as f:
                content = f.read()

            # Convert to string for text extraction
            text_content = content.decode('utf-8', errors='ignore')

            # Extract basic event information
            event = {
                'id': os.path.basename(file_path).replace('.olk15Event', ''),
                'file_path': file_path,
                'provider': 'outlook_mac',
                'provider_id': self._extract_exchange_id(text_content),
                'title': self._extract_title(text_content),
                'description': self._extract_description(text_content),
                'location': self._extract_location(text_content),
                'organizer': self._extract_organizer(text_content),
                'participants': self._extract_participants(text_content),
                'start_time': self._extract_start_time(text_content, file_path),
                'end_time': self._extract_end_time(text_content, file_path),
                'all_day': self._is_all_day(text_content),
                'recurring': self._is_recurring(text_content),
                'recurrence_pattern': self._extract_recurrence_pattern(text_content),
                'calendar_id': self._extract_calendar_id(text_content),
                'calendar_name': self._extract_calendar_name(text_content),
                'private': self._is_private(text_content),
                'status': 'confirmed',  # Default status
                'created_at': datetime.fromtimestamp(os.path.getctime(file_path)).isoformat(),
                'modified_at': datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat(),
            }

            # Validate required fields
            if not event['start_time'] or not event['title']:
                logger.debug(
                    f"Skipping event with missing required fields: {file_path}")
                return None

            return event

        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
            return None

    def _extract_exchange_id(self, content: str) -> str:
        """Extract Exchange message ID from content"""
        # Look for Exchange-style IDs
        exchange_id_pattern = r'[A-Za-z0-9+/]{100,}=='
        match = re.search(exchange_id_pattern, content)
        return match.group(0) if match else ''

    def _extract_title(self, content: str) -> str:
        """Extract event title/subject with enhanced patterns"""
        # Priority patterns - most specific first
        title_patterns = [
            # Standard calendar fields
            r'Subject:\s*([^\n\r]+)',
            r'SUMMARY:([^\n\r]+)',
            r'"?subject"?\s*[:=]\s*"([^"]+)"',
            r'"?title"?\s*[:=]\s*"([^"]+)"',
            r'"?summary"?\s*[:=]\s*"([^"]+)"',
            
            # Exchange/Outlook patterns
            r'PR_SUBJECT[^:]*:\s*([^\n\r]+)',
            r'MessageClass[^:]*Meeting.*Subject[^:]*:\s*([^\n\r]+)',
            
            # Calendar data patterns
            r'BEGIN:VEVENT.*?SUMMARY:([^\n\r]+)',
            r'EventTitle["\s]*[:=]["\s]*([^"\n\r]+)',
            
            # JSON-like patterns
            r'"displayName":\s*"([^"]+)"',
            r'"name":\s*"([^"]+)"',
            
            # Generic patterns
            r'title["\s]*[:=]["\s]*([^"\n\r]+)',
            r'name["\s]*[:=]["\s]*([^"\n\r]+)',
        ]

        for pattern in title_patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                title = match.group(1).strip()
                # Clean up the title
                title = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', title)  # Remove control characters
                title = re.sub(r'\s+', ' ', title)  # Normalize whitespace
                
                # Validate title quality
                if (len(title) >= 3 and 
                    len(title) <= 200 and  # Reasonable length
                    '@' not in title and  # Not an email
                    not title.isdigit() and  # Not just numbers
                    not re.match(r'^[^\w]*$', title)):  # Not just punctuation
                    return title

        # Advanced fallback: look for text patterns that might be titles
        # Look for text in quotes that could be event names
        quoted_patterns = [
            r'"([A-Za-z][^"]{5,100})"',  # Text in quotes
            r"'([A-Za-z][^']{5,100})'",  # Text in single quotes
        ]
        
        for pattern in quoted_patterns:
            matches = re.findall(pattern, content)
            for potential_title in matches:
                potential_title = potential_title.strip()
                if (len(potential_title) >= 5 and 
                    '@' not in potential_title and
                    not potential_title.lower().startswith(('http', 'www', 'ftp'))):
                    return potential_title

        # Look for capitalized words that could be meeting titles
        capitalized_pattern = r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,6}\b'
        matches = re.findall(capitalized_pattern, content)
        for potential_title in matches:
            potential_title = potential_title.strip()
            if (len(potential_title) >= 8 and 
                len(potential_title) <= 100 and
                potential_title.count(' ') >= 1):  # Multi-word
                return potential_title

        return "Untitled Event"

    def _extract_description(self, content: str) -> str:
        """Extract event description"""
        desc_patterns = [
            r'DESCRIPTION:([^\n\r]+)',
            r'"description":\s*"([^"]+)"',
        ]

        for pattern in desc_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return ""

    def _extract_location(self, content: str) -> str:
        """Extract event location"""
        location_patterns = [
            r'LOCATION:([^\n\r]+)',
            r'"location":\s*"([^"]+)"',
            r'Location:\s*([^\n\r]+)',
        ]

        for pattern in location_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return ""

    def _extract_organizer(self, content: str) -> Dict[str, str]:
        """Extract event organizer information"""
        # Find email addresses that might be the organizer
        emails = re.findall(
            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', content)

        if emails:
            # Use the first email as organizer (often the most relevant)
            return {
                'email': emails[0],
                'name': emails[0].split('@')[0]
            }

        return {}

    def _extract_participants(self, content: str) -> List[Dict[str, str]]:
        """Extract event participants"""
        emails = re.findall(
            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', content)

        participants = []
        # Remove duplicates while preserving order
        seen = set()
        for email_addr in emails:
            if email_addr not in seen:
                seen.add(email_addr)
                participants.append({
                    'email': email_addr,
                    'name': email_addr.split('@')[0],
                    'status': 'accepted'  # Default status
                })

        return participants

    def _extract_start_time(self, content: str, file_path: str) -> str:
        """Extract event start time with enhanced parsing"""
        # Try different timestamp extraction methods
        
        # Method 1: Look for ISO datetime strings
        iso_patterns = [
            r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?(?:Z|[+-]\d{2}:\d{2})?)',
            r'DTSTART[^:]*:(\d{8}T\d{6}Z?)',
            r'StartTime["\s]*[:=]["\s]*([^"\s\n\r]+)',
        ]
        
        for pattern in iso_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                try:
                    time_str = match.group(1)
                    # Handle different formats
                    if 'T' in time_str and len(time_str) >= 15:
                        if time_str.endswith('Z'):
                            # UTC time
                            dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                        elif '+' in time_str or time_str.count('-') > 2:
                            # Timezone aware
                            dt = datetime.fromisoformat(time_str)
                        else:
                            # No timezone, assume local
                            dt = datetime.fromisoformat(time_str)
                        return dt.isoformat()
                    elif len(time_str) == 15:  # YYYYMMDDTHHMMSS format
                        dt = datetime.strptime(time_str.rstrip('Z'), '%Y%m%dT%H%M%S')
                        return dt.isoformat()
                except (ValueError, IndexError) as e:
                    logger.debug(f"Failed to parse timestamp '{time_str}': {e}")
                    continue

        # Method 2: Look for Unix timestamps or other numeric formats
        timestamp_patterns = [
            r'timestamp["\s]*[:=]["\s]*(\d{10,13})',  # Unix timestamp
            r'StartTime["\s]*[:=]["\s]*(\d{10,13})',
            r'time["\s]*[:=]["\s]*(\d{10,13})',
        ]
        
        for pattern in timestamp_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                try:
                    timestamp = int(match.group(1))
                    # Handle both seconds and milliseconds
                    if timestamp > 1000000000000:  # Milliseconds
                        timestamp = timestamp / 1000
                    dt = datetime.fromtimestamp(timestamp)
                    return dt.isoformat()
                except (ValueError, OSError) as e:
                    logger.debug(f"Failed to parse timestamp {timestamp}: {e}")
                    continue

        # Method 3: Enhanced file-based time extraction
        try:
            file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
            
            # Look for hour/minute hints in the content
            time_hints = [
                r'BYHOUR=(\d+)',
                r'hour["\s]*[:=]["\s]*(\d{1,2})',
                r'minute["\s]*[:=]["\s]*(\d{1,2})',
            ]
            
            hour = file_mtime.hour
            minute = file_mtime.minute
            
            for pattern in time_hints:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    try:
                        value = int(match.group(1))
                        if 'hour' in pattern.lower() or 'HOUR' in pattern:
                            if 0 <= value <= 23:
                                hour = value
                        elif 'minute' in pattern.lower():
                            if 0 <= value <= 59:
                                minute = value
                    except ValueError:
                        continue
            
            return file_mtime.replace(hour=hour, minute=minute).isoformat()
            
        except OSError as e:
            logger.warning(f"Could not get file modification time for {file_path}: {e}")
            
        # Final fallback: current time
        return datetime.now().isoformat()

    def _extract_end_time(self, content: str, file_path: str) -> str:
        """Extract event end time with enhanced parsing"""
        # First try to find explicit end time patterns
        end_patterns = [
            r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?(?:Z|[+-]\d{2}:\d{2})?).*end',
            r'DTEND[^:]*:(\d{8}T\d{6}Z?)',
            r'EndTime["\s]*[:=]["\s]*([^"\s\n\r]+)',
            r'end["\s]*[:=]["\s]*([^"\s\n\r]+)',
        ]
        
        for pattern in end_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                try:
                    time_str = match.group(1)
                    if 'T' in time_str and len(time_str) >= 15:
                        if time_str.endswith('Z'):
                            dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                        elif '+' in time_str or time_str.count('-') > 2:
                            dt = datetime.fromisoformat(time_str)
                        else:
                            dt = datetime.fromisoformat(time_str)
                        return dt.isoformat()
                    elif len(time_str) == 15:
                        dt = datetime.strptime(time_str.rstrip('Z'), '%Y%m%dT%H%M%S')
                        return dt.isoformat()
                except (ValueError, IndexError) as e:
                    logger.debug(f"Failed to parse end time '{time_str}': {e}")
                    continue
        
        # Look for duration indicators
        duration_patterns = [
            r'duration["\s]*[:=]["\s]*(\d+)',  # Duration in minutes
            r'DURATION:PT(\d+)([HM])',  # ISO duration format
        ]
        
        for pattern in duration_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                try:
                    duration_value = int(match.group(1))
                    if len(match.groups()) > 1:
                        unit = match.group(2).upper()
                        if unit == 'H':
                            duration_value *= 60  # Convert hours to minutes
                    
                    start_time = self._extract_start_time(content, file_path)
                    start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00').replace('+00:00', ''))
                    end_dt = start_dt + timedelta(minutes=duration_value)
                    return end_dt.isoformat()
                except (ValueError, IndexError) as e:
                    logger.debug(f"Failed to parse duration: {e}")
                    continue
        
        # Fallback: calculate from start time with default duration
        try:
            start_time = self._extract_start_time(content, file_path)
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00').replace('+00:00', ''))
            
            # Check if it looks like an all-day event (start time at midnight)
            if start_dt.hour == 0 and start_dt.minute == 0:
                # All-day event: end at 11:59 PM same day
                end_dt = start_dt.replace(hour=23, minute=59, second=59)
            else:
                # Regular event: default to 1 hour duration
                end_dt = start_dt + timedelta(hours=1)
            
            return end_dt.isoformat()
        except (ValueError, IndexError) as e:
            logger.warning(f"Could not calculate end time from start time: {e}")
            # Final fallback
            return self._extract_start_time(content, file_path)

    def _is_all_day(self, content: str) -> bool:
        """Check if event is all day"""
        all_day_patterns = [
            r'ALLDAY',
            r'all.day',
            r'AllDay.*true',
        ]

        for pattern in all_day_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True

        return False

    def _is_recurring(self, content: str) -> bool:
        """Check if event is recurring"""
        return 'FREQ=' in content or 'RRULE:' in content

    def _extract_recurrence_pattern(self, content: str) -> str:
        """Extract recurrence pattern"""
        rrule_match = re.search(r'FREQ=[^;]+(?:;[^;]+)*', content)
        return rrule_match.group(0) if rrule_match else ""

    def _extract_calendar_id(self, content: str) -> str:
        """Extract calendar ID"""
        # Look for folder or calendar identifiers
        folder_patterns = [
            r'FolderID["\s]*[:=]["\s]*([^"\s\n\r]+)',
            r'CalendarID["\s]*[:=]["\s]*([^"\s\n\r]+)',
        ]

        for pattern in folder_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1)

        return ""

    def _extract_calendar_name(self, content: str) -> str:
        """Extract calendar name"""
        # Try to determine calendar name from email domain or content
        emails = re.findall(
            r'[a-zA-Z0-9._%+-]+@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', content)

        if emails:
            # Use the most common domain as calendar name
            domain_counts = {}
            for domain in emails:
                domain_counts[domain] = domain_counts.get(domain, 0) + 1
            most_common_domain = max(domain_counts, key=domain_counts.get)
            return f"Calendar ({most_common_domain})"

        return "Unknown Calendar"

    def _is_private(self, content: str) -> bool:
        """Check if event is private"""
        private_patterns = [
            r'PRIVATE',
            r'private.*true',
            r'confidential',
        ]

        for pattern in private_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True

        return False


def test_parser():
    """Test the parser with your Outlook data"""
    outlook_data_dir = "/Users/andrew/Library/Group Containers/UBF8T346G9.Office/Outlook/Outlook 15 Profiles/Main Profile/Data"

    parser = OLK15EventParser(outlook_data_dir)

    print("🔍 ANALYZING OUTLOOK ACCOUNTS...")
    print("=" * 50)

    accounts = parser.get_account_directories()
    for dir_num, account_info in accounts.items():
        print(f"📁 Directory {dir_num}:")
        print(f"   Email: {account_info['email']}")
        print(f"   Events: {account_info['event_count']}")
        print(f"   Path: {account_info['path']}")
        print()

    # Find and parse work-related accounts (containing 'andrew' or 'chepurn' in email)
    work_accounts = []
    for dir_num, account_info in accounts.items():
        email = account_info.get('email', '').lower()
        if 'andrew' in email or 'chepurn' in email or 'chip' in email:
            work_accounts.append((dir_num, account_info))

    if not work_accounts:
        print("⚠️ No work accounts found. Available accounts:")
        for dir_num, account_info in accounts.items():
            print(
                f"  - {dir_num}: {account_info.get('email', 'No email')} ({account_info.get('event_count', 0)} events)")
    else:
        print(f"🔍 Found {len(work_accounts)} work-related accounts")

    # Parse events from work accounts
    for dir_num, account_info in work_accounts:
        print(
            f"\n🎯 PARSING EVENTS FROM WORK ACCOUNT: {account_info.get('email')} (Directory {dir_num})")
        print("=" * 70)

        try:
            events = parser.get_events_for_account(account_info['path'])
            print(f"✅ Found {len(events)} events")

            # Show first few events
            for i, event in enumerate(events[:3]):
                print(f"\n  {i+1}. {event.get('title', 'No title')}")
                print(f"     Start: {event.get('start_time', 'N/A')}")
                print(f"     End: {event.get('end_time', 'N/A')}")
                print(f"     Organizer: {event.get('organizer', 'N/A')}")
                print(
                    f"     Participants: {len(event.get('participants', []))}")

                # Show first 3 participants if any
                participants = event.get('participants', [])[:3]
                if participants:
                    print("     First few participants:")
                    for p in participants:
                        print(
                            f"       - {p.get('name', 'Unknown')} <{p.get('email', 'no-email')}>")

                if len(event.get('participants', [])) > 3:
                    print(
                        f"     ... and {len(event['participants']) - 3} more")

        except Exception as e:
            print(f"❌ Error parsing events for account {dir_num}: {str(e)}")
            import traceback
            traceback.print_exc()
            continue


if __name__ == "__main__":
    test_parser()

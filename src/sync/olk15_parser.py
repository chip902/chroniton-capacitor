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
        except:
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
        """Extract event title/subject"""
        # Try multiple patterns to find the title

        # Look for common title indicators
        title_patterns = [
            r'Subject:\s*([^\n\r]+)',
            r'SUMMARY:([^\n\r]+)',
            r'"title":\s*"([^"]+)"',
        ]

        for pattern in title_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        # Fallback: look for text near email addresses (often meeting titles)
        email_context = re.search(
            r'@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}[^a-zA-Z0-9@]*([A-Za-z][^\n\r]{5,50})', content)
        if email_context:
            potential_title = email_context.group(1).strip()
            if len(potential_title) > 5 and not '@' in potential_title:
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
        for email in emails:
            if email not in seen:
                seen.add(email)
                participants.append({
                    'email': email,
                    'name': email.split('@')[0],
                    'status': 'accepted'  # Default status
                })

        return participants

    def _extract_start_time(self, content: str, file_path: str) -> str:
        """Extract event start time"""
        # Try to find timezone and time information
        timezone_pattern = r'[-+]\d{4}'
        tz_match = re.search(timezone_pattern, content)

        # For now, use file modification time as approximation
        # This could be improved by parsing binary timestamp data
        file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))

        # Look for recurrence patterns that might contain time info
        time_patterns = [
            r'BYHOUR=(\d+)',
            r'T(\d{6})Z',
            r'(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})',
        ]

        for pattern in time_patterns:
            match = re.search(pattern, content)
            if match:
                try:
                    # Try to construct a proper datetime
                    if pattern == r'BYHOUR=(\d+)':
                        hour = int(match.group(1))
                        return file_mtime.replace(hour=hour).isoformat()
                    elif pattern == r'T(\d{6})Z':
                        time_str = match.group(1)
                        hour = int(time_str[:2])
                        minute = int(time_str[2:4])
                        return file_mtime.replace(hour=hour, minute=minute).isoformat()
                except:
                    continue

        # Default to file modification time
        return file_mtime.isoformat()

    def _extract_end_time(self, content: str, file_path: str) -> str:
        """Extract event end time"""
        start_time = self._extract_start_time(content, file_path)
        try:
            start_dt = datetime.fromisoformat(
                start_time.replace('Z', '+00:00').replace('+00:00', ''))
            # Default to 1 hour duration
            end_dt = start_dt + timedelta(hours=1)
            return end_dt.isoformat()
        except:
            return start_time

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

    # Test parsing events from your most active accounts
    for dir_num in ['4', '7']:  # chip@prj-3.com and andrew@chip-hosting.com
        if dir_num in accounts:
            print(f"🎯 PARSING EVENTS FROM DIRECTORY {dir_num}...")
            events = parser.get_events_for_account(accounts[dir_num]['path'])
            print(f"Found {len(events)} events")

            # Show first few events
            for i, event in enumerate(events[:3]):
                print(f"  {i+1}. {event['title']}")
                print(f"     Start: {event['start_time']}")
                print(f"     Organizer: {event['organizer']}")
                print(f"     Participants: {len(event['participants'])}")
                print()


if __name__ == "__main__":
    test_parser()

"""
CalDAV Client for Mailcow Integration

This module provides CalDAV functionality to sync with Mailcow calendar servers.
"""

import requests
from typing import List, Dict, Any
from datetime import datetime, timezone
import uuid
from urllib.parse import urljoin
import xml.etree.ElementTree as ET
from icalendar import Calendar, Event, vText
import logging

logger = logging.getLogger(__name__)


class CalDAVClient:
    """CalDAV client for syncing with Mailcow calendar servers"""

    def __init__(self, server_url: str, username: str, password: str):
        """
        Initialize CalDAV client

        Args:
            server_url: CalDAV server URL (e.g., https://mail.yourdomain.com/SOGo/dav/)
            username: Mailcow username
            password: Mailcow password
        """
        self.server_url = server_url.rstrip('/')
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.auth = (username, password)
        self.session.headers.update({
            'User-Agent': 'Chroniton-Capacitor/1.0',
            'Content-Type': 'application/xml; charset=utf-8'
        })

    def discover_calendars(self) -> List[Dict[str, str]]:
        """
        Discover available calendars for the user

        Returns:
            List of calendar dictionaries with name, url, and description
        """
        try:
            # CalDAV PROPFIND to discover calendars
            propfind_body = '''<?xml version="1.0" encoding="utf-8" ?>
            <D:propfind xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
                <D:prop>
                    <D:displayname />
                    <C:calendar-description />
                    <D:resourcetype />
                </D:prop>
            </D:propfind>'''

            # Try common CalDAV paths (including Mailcow/SOGo specific paths)
            potential_paths = [
                # Mailcow/SOGo with email as username
                f'/SOGo/dav/{self.username}/Calendar/',
                f'/caldav/{self.username}/',
                f'/dav/{self.username}/calendar/',
                f'/calendar.php/calendars/{self.username}/',
                # Also try without the username for discovery
                '/SOGo/dav/',
                '/caldav/',
                '/dav/'
            ]

            calendars = []

            for path in potential_paths:
                url = urljoin(self.server_url, path)
                logger.info(f"Trying CalDAV discovery at: {url}")
                try:
                    response = self.session.request(
                        'PROPFIND',
                        url,
                        data=propfind_body,
                        headers={'Depth': '1'}
                    )

                    logger.info(
                        f"PROPFIND response for {url}: {response.status_code}")

                    if response.status_code == 207:  # Multi-Status
                        # Parse WebDAV XML response
                        root = ET.fromstring(response.text)

                        for response_elem in root.findall('.//{DAV:}response'):
                            href_elem = response_elem.find('.//{DAV:}href')
                            displayname_elem = response_elem.find(
                                './/{DAV:}displayname')
                            resourcetype_elem = response_elem.find(
                                './/{DAV:}resourcetype')

                            # Check if this is a calendar resource
                            if (resourcetype_elem is not None and
                                    resourcetype_elem.find('.//{urn:ietf:params:xml:ns:caldav}calendar') is not None):

                                calendar_name = displayname_elem.text if displayname_elem is not None else 'Unnamed Calendar'
                                calendar_url = href_elem.text if href_elem is not None else ''

                                calendars.append({
                                    'name': calendar_name,
                                    'url': urljoin(self.server_url, calendar_url),
                                    'description': f'CalDAV calendar: {calendar_name}'
                                })

                        if calendars:
                            break  # Found calendars, stop trying other paths

                except Exception as e:
                    logger.warning(
                        f"Failed to discover calendars at {url}: {e}")
                    continue

            return calendars

        except Exception as e:
            logger.error(f"CalDAV calendar discovery failed: {e}")
            return []

    def create_event(self, calendar_url: str, event_data: Dict[str, Any]) -> bool:
        """
        Create a new event in the specified calendar

        Args:
            calendar_url: URL of the target calendar
            event_data: Event data dictionary

        Returns:
            True if successful, False otherwise
        """
        try:
            # Generate unique event ID
            event_id = str(uuid.uuid4())
            event_url = f"{calendar_url.rstrip('/')}/{event_id}.ics"

            # Create iCalendar event
            cal = Calendar()
            cal.add('prodid', '-//Chroniton Capacitor//Calendar Sync//EN')
            cal.add('version', '2.0')

            event = Event()
            event.add('uid', event_id)
            event.add('dtstart', datetime.fromisoformat(
                event_data['start_time'].replace('Z', '+00:00')))
            event.add('dtend', datetime.fromisoformat(
                event_data['end_time'].replace('Z', '+00:00')))
            event.add('summary', vText(event_data.get('title', 'No Title')))
            event.add('description', vText(event_data.get('description', '')))

            if event_data.get('location'):
                event.add('location', vText(event_data['location']))

            event.add('dtstamp', datetime.now(timezone.utc))
            event.add('created', datetime.now(timezone.utc))
            event.add('last-modified', datetime.now(timezone.utc))

            cal.add_component(event)

            # Send PUT request to create event
            response = self.session.put(
                event_url,
                data=cal.to_ical().decode('utf-8'),
                headers={'Content-Type': 'text/calendar; charset=utf-8'}
            )

            if response.status_code in [201, 204]:
                logger.info(
                    f"Successfully created CalDAV event: {event_data['title']}")
                return True
            else:
                logger.error(
                    f"Failed to create CalDAV event: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"Error creating CalDAV event: {e}")
            return False

    def update_event(self, event_url: str, event_data: Dict[str, Any]) -> bool:
        """
        Update an existing event

        Args:
            event_url: URL of the event to update
            event_data: Updated event data

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get existing event first to preserve UID
            response = self.session.get(event_url)
            if response.status_code != 200:
                return False

            # Parse existing calendar
            existing_cal = Calendar.from_ical(response.content)
            existing_event = None
            for component in existing_cal.walk():
                if component.name == "VEVENT":
                    existing_event = component
                    break

            if not existing_event:
                return False

            # Create updated calendar
            cal = Calendar()
            cal.add('prodid', '-//Chroniton Capacitor//Calendar Sync//EN')
            cal.add('version', '2.0')

            event = Event()
            event.add('uid', existing_event['uid'])  # Preserve original UID
            event.add('dtstart', datetime.fromisoformat(
                event_data['start_time'].replace('Z', '+00:00')))
            event.add('dtend', datetime.fromisoformat(
                event_data['end_time'].replace('Z', '+00:00')))
            event.add('summary', vText(event_data.get('title', 'No Title')))
            event.add('description', vText(event_data.get('description', '')))

            if event_data.get('location'):
                event.add('location', vText(event_data['location']))

            event.add('dtstamp', datetime.now(timezone.utc))
            event.add('last-modified', datetime.now(timezone.utc))

            # Preserve created timestamp if it exists
            if 'created' in existing_event:
                event.add('created', existing_event['created'])
            else:
                event.add('created', datetime.now(timezone.utc))

            cal.add_component(event)

            # Send PUT request to update event
            response = self.session.put(
                event_url,
                data=cal.to_ical().decode('utf-8'),
                headers={'Content-Type': 'text/calendar; charset=utf-8'}
            )

            if response.status_code in [200, 204]:
                logger.info(
                    f"Successfully updated CalDAV event: {event_data['title']}")
                return True
            else:
                logger.error(
                    f"Failed to update CalDAV event: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"Error updating CalDAV event: {e}")
            return False

    def delete_event(self, event_url: str) -> bool:
        """
        Delete an event

        Args:
            event_url: URL of the event to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            response = self.session.delete(event_url)

            if response.status_code in [200, 204]:
                logger.info(f"Successfully deleted CalDAV event: {event_url}")
                return True
            else:
                logger.error(
                    f"Failed to delete CalDAV event: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"Error deleting CalDAV event: {e}")
            return False

    def test_connection(self) -> bool:
        """
        Test the CalDAV connection

        Returns:
            True if connection is successful, False otherwise
        """
        try:
            logger.info(f"Testing CalDAV connection to {self.server_url}")

            # First try a simple OPTIONS request to test basic connectivity
            try:
                response = self.session.options(self.server_url)
                logger.info(f"OPTIONS request status: {response.status_code}")
                # 405 is OK for OPTIONS
                if response.status_code not in [200, 204, 405]:
                    logger.warning(
                        f"Unexpected OPTIONS response: {response.status_code}")
            except Exception as e:
                logger.error(f"Basic connectivity test failed: {e}")
                return False

            # Try to discover calendars
            calendars = self.discover_calendars()
            logger.info(f"Discovered {len(calendars)} calendars")

            # Return True if we can at least connect, even if no calendars found
            # (user might not have calendars set up yet)
            return True

        except Exception as e:
            logger.error(f"CalDAV connection test failed: {e}")
            return False

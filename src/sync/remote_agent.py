"""
Remote Calendar Synchronization Agent

This module provides a standalone agent that can run in isolated environments
to synchronize calendar data with the central calendar service.
"""

import os
import json
import asyncio
import logging
import argparse
import aiohttp
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
import platform
import socket

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("calendar_agent.log")
    ]
)
logger = logging.getLogger("calendar_agent")


class RemoteCalendarAgent:
    """
    Agent for synchronizing calendars from isolated environments

    This agent can:
    1. Connect to calendar services in isolated environments
    2. Collect calendar data and events
    3. Send data to the central calendar service
    4. Operate in various synchronization modes (API, file, etc.)
    """

    def __init__(self, config_path: str, central_api_url: str = None):
        """Initialize the calendar agent"""
        self.config_path = config_path
        self.config = None
        self.central_api_url = central_api_url
        self.agent_id = None
        self.agent_name = None
        self.environment = platform.node()
        self.running = False
        self.sync_interval = 60  # Default to 60 minutes
        self.http_session = None

        # Store last sync tokens for incremental sync
        self.sync_tokens = {}

    async def initialize(self):
        """Initialize the agent"""
        # Load configuration
        await self.load_config()

        # Create HTTP session
        self.http_session = aiohttp.ClientSession()

        # Register with central service if needed
        if not self.agent_id:
            await self.register_with_central_service()

    async def load_config(self):
        """Load agent configuration from file"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r") as f:
                    self.config = json.load(f)

                # Extract agent details
                self.agent_id = self.config.get("agent_id")
                self.agent_name = self.config.get(
                    "agent_name", f"Agent-{socket.gethostname()}")
                self.environment = self.config.get(
                    "environment", self.environment)
                self.central_api_url = self.config.get(
                    "central_api_url", self.central_api_url)
                self.sync_interval = self.config.get(
                    "sync_interval_minutes", 60)

                # Load any saved sync tokens
                self.sync_tokens = self.config.get("sync_tokens", {})

                logger.info(
                    f"Configuration loaded: Agent ID: {self.agent_id}, Name: {self.agent_name}")
            else:
                # Create initial config
                self.config = {
                    "agent_id": str(uuid.uuid4()),
                    "agent_name": f"Agent-{socket.gethostname()}",
                    "environment": self.environment,
                    "central_api_url": self.central_api_url,
                    "sync_interval_minutes": self.sync_interval,
                    "sync_tokens": {},
                    "calendar_sources": []
                }
                self.agent_id = self.config["agent_id"]
                await self.save_config()

                logger.info(
                    f"Created new configuration with Agent ID: {self.agent_id}")

        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            raise

    async def save_config(self):
        """Save agent configuration to file"""
        try:
            # Update sync tokens in config
            self.config["sync_tokens"] = self.sync_tokens

            with open(self.config_path, "w") as f:
                json.dump(self.config, f, indent=2, default=str)

            logger.debug("Configuration saved")
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")

    async def register_with_central_service(self):
        """Register this agent with the central calendar service"""
        if not self.central_api_url:
            logger.warning("Cannot register: central_api_url not configured")
            return False

        try:
            # Prepare registration data
            agent_data = {
                "id": self.agent_id,
                "name": self.agent_name,
                "environment": self.environment,
                "agent_type": "python",
                "interval_minutes": self.sync_interval,
                "capabilities": ["calendar_sync"],
                "config": {
                    "version": "1.0.0",
                    "platform": platform.system().lower(),
                    "python_version": platform.python_version()
                }
            }

            # Register with central service
            url = f"{self.central_api_url}/sync/agents/register"
            async with self.http_session.post(url, json=agent_data) as response:
                result = await response.json()

                if response.status == 201:  # 201 Created
                    # Update agent ID if it was assigned by the central service
                    if "id" in result and result["id"] != self.agent_id:
                        self.agent_id = result["id"]
                        self.config["agent_id"] = self.agent_id
                        await self.save_config()

                    logger.info(
                        f"Agent registered successfully with ID: {self.agent_id}")
                    return True
                else:
                    error_detail = result.get("detail", "No details provided")
                    logger.error(
                        f"Failed to register agent: {response.status} - {error_detail}"
                    )
                    return False

        except Exception as e:
            logger.error(f"Error registering with central service: {e}")
            return False

    async def send_heartbeat(self, include_events: bool = False):
        """Send heartbeat to central service"""
        if not self.central_api_url or not self.agent_id:
            logger.warning(
                "Cannot send heartbeat: missing central_api_url or agent_id")
            return None

        try:
            # Prepare heartbeat data
            heartbeat_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "status": "active",
                "environment": self.environment,
                "stats": {
                    "cpu_percent": 0,  # TODO: Add system stats
                    "memory_percent": 0,
                    "events_processed": 0
                }
            }

            # Include events if requested
            if include_events:
                events = await self.collect_all_events()
                if events:
                    heartbeat_data["events"] = events

            # Send heartbeat to central service
            url = f"{self.central_api_url}/sync/agents/{self.agent_id}/heartbeat"
            async with self.http_session.post(url, json=heartbeat_data) as response:
                result = await response.json()

                if response.status == 200:
                    logger.info("Heartbeat sent successfully")

                    # Check for pending updates from central service
                    if result and "pending_updates" in result and result["pending_updates"]:
                        logger.info(
                            f"Received {len(result['pending_updates'])} pending updates")
                        await self.process_pending_updates(result["pending_updates"])

                    return result
                else:
                    error_detail = result.get("detail", "No details provided")
                    logger.error(
                        f"Heartbeat failed: {response.status} - {error_detail}"
                    )

                    # If we get a 404, the agent might need to re-register
                    if response.status == 404:
                        logger.info(
                            "Agent not found, attempting to re-register...")
                        if await self.register_with_central_service():
                            # Retry the heartbeat after successful registration
                            return await self.send_heartbeat(include_events)

                    return None

        except Exception as e:
            logger.error(f"Error sending heartbeat: {e}")
            return None

    async def collect_all_events(self) -> List[Dict[str, Any]]:
        """Collect events from all configured calendar sources"""
        all_events = []

        for source in self.config.get("calendar_sources", []):
            try:
                source_type = source.get("type")

                if source_type == "google":
                    events = await self.collect_google_events(source)
                elif source_type == "microsoft":
                    events = await self.collect_microsoft_events(source)
                elif source_type == "exchange":
                    events = await self.collect_exchange_events(source)
                elif source_type == "ical":
                    events = await self.collect_ical_events(source)
                elif source_type == "outlook":
                    events = await self.collect_outlook_events(source)
                elif source_type == "outlook_mac":
                    events = await self._collect_outlook_mac_events(source)
                elif source_type == "custom":
                    events = await self.collect_custom_events(source)
                else:
                    logger.warning(f"Unknown source type: {source_type}")
                    events = []

                # Add events from this source
                all_events.extend(events)

                # Update last sync time for this source
                source["last_sync"] = datetime.utcnow().isoformat()

            except Exception as e:
                logger.error(
                    f"Error collecting events from source {source.get('name', 'unknown')}: {e}")

        # Save updated configuration
        await self.save_config()

        return all_events

    async def collect_google_events(self, source: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Collect events from a Google Calendar source"""
        try:
            # This is a placeholder for real implementation
            # In a real agent, this would use the Google Calendar API client
            logger.info(
                f"Would collect events from Google Calendar: {source.get('name')}")

            # Example implementation:
            # from googleapiclient.discovery import build
            # credentials = get_credentials_from_source(source)
            # service = build('calendar', 'v3', credentials=credentials)
            # events_result = service.events().list(calendarId=source.get('calendar_id'), ...).execute()

            # For now, return empty list
            return []

        except Exception as e:
            logger.error(f"Error collecting Google events: {e}")
            return []

    async def collect_microsoft_events(self, source: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Collect events from a Microsoft Calendar source"""
        try:
            # This is a placeholder for real implementation
            # In a real agent, this would use the Microsoft Graph SDK
            logger.info(
                f"Would collect events from Microsoft Calendar: {source.get('name')}")

            # Example implementation:
            # import msal
            # from msgraph.core import GraphClient
            # app = msal.ConfidentialClientApplication(...)
            # graph_client = GraphClient(credentials=...)
            # response = await graph_client.get('/me/calendars/{id}/events')

            # For now, return empty list
            return []

        except Exception as e:
            logger.error(f"Error collecting Microsoft events: {e}")
            return []

    async def collect_exchange_events(self, source: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Collect events from an Exchange server"""
        try:
            # This is a placeholder for real implementation
            # In a real agent, this would use the Exchange Web Services API
            logger.info(
                f"Would collect events from Exchange: {source.get('name')}")

            # Example implementation:
            # from exchangelib import Credentials, Account
            # credentials = Credentials(username=source.get('username'), password=source.get('password'))
            # account = Account(primary_smtp_address=source.get('email'), credentials=credentials, ...)
            # events = list(account.calendar.filter(...))

            # For now, return empty list
            return []

        except Exception as e:
            logger.error(f"Error collecting Exchange events: {e}")
            return []

    async def collect_ical_events(self, source: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Collect events from an iCal file or URL"""
        try:
            # This is a placeholder for real implementation
            # In a real agent, this would parse iCal files
            logger.info(
                f"Would collect events from iCal: {source.get('name')}")

            # Example implementation:
            # from icalendar import Calendar
            # ical_data = get_ical_data_from_source(source)
            # cal = Calendar.from_ical(ical_data)
            # events = [e for e in cal.walk('VEVENT')]

            # For now, return empty list
            return []

        except Exception as e:
            logger.error(f"Error collecting iCal events: {e}")
            return []

    async def _collect_outlook_windows_events(self, source: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Collect events from Outlook on Windows using COM interface"""
        try:
            import win32com.client
            import pythoncom
            from datetime import datetime, timedelta

            logger.info(
                f"Collecting events from Outlook calendar (Windows): {source.get('name')}")

            # Initialize COM for this thread
            pythoncom.CoInitialize()
            try:
                # Connect to Outlook
                outlook = win32com.client.Dispatch("Outlook.Application")
                namespace = outlook.GetNamespace("MAPI")

                # Get the calendar folder
                calendar_name = source.get("calendar_name", "Calendar")
                calendar = None

                # Try to find the calendar by name
                # 9 = olFolderCalendar
                for folder in namespace.GetDefaultFolder(9).Folders:
                    if folder.Name == calendar_name:
                        calendar = folder
                        break

                if not calendar:
                    logger.warning(
                        f"Calendar '{calendar_name}' not found. Using default calendar.")
                    calendar = namespace.GetDefaultFolder(
                        9)  # Default calendar

                # Get appointments from the last 30 days and next 30 days
                start_date = (datetime.now() - timedelta(days=30)
                              ).strftime('%m/%d/%Y')
                end_date = (datetime.now() + timedelta(days=30)
                            ).strftime('%m/%d/%Y')

                # Create filter
                filter_str = f"[Start] >= '{start_date}' AND [End] <= '{end_date}'"
                appointments = calendar.Items.Restrict(filter_str)
                events = []

                for appointment in appointments:
                    try:
                        # Skip recurring appointments for now
                        if appointment.IsRecurring:
                            continue

                        event = {
                            "id": appointment.EntryID,
                            "title": appointment.Subject,
                            "description": appointment.Body,
                            "start": appointment.Start.isoformat(),
                            "end": appointment.End.isoformat(),
                            "location": appointment.Location,
                            "all_day": appointment.AllDayEvent,
                            "recurring": False,
                            "source": "outlook",
                            "source_id": appointment.EntryID,
                            "calendar_id": source.get("id", ""),
                            "calendar_name": calendar_name,
                            "status": "confirmed" if appointment.MeetingStatus == 0 else "tentative",
                            "participants": [],
                            "created_at": appointment.CreationTime.isoformat() if hasattr(appointment, "CreationTime") else None,
                            "updated_at": appointment.LastModificationTime.isoformat() if hasattr(appointment, "LastModificationTime") else None,
                        }
                        # Add attendees if available
                        if hasattr(appointment, "Recipients"):
                            for recipient in appointment.Recipients:
                                participant = {
                                    "email": recipient.Address if hasattr(recipient, "Address") else None,
                                    "name": recipient.Name if hasattr(recipient, "Name") else None,
                                    "response_status": "accepted" if recipient.MeetingResponseStatus == 3 else "tentative"
                                }
                                event["participants"].append(participant)

                        events.append(event)
                    except Exception as e:
                        logger.error(f"Error processing appointment: {e}")
                        continue

                logger.info(
                    f"Collected {len(events)} events from Outlook calendar '{calendar_name}'")
                return events

            except Exception as e:
                logger.error(f"Error accessing Outlook: {e}")
                return []
            finally:
                # Always uninitialize COM
                pythoncom.CoUninitialize()

        except ImportError:
            logger.error(
                "win32com package not available - required for Outlook integration on Windows")
            return []

    async def _collect_outlook_mac_events(self, source: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Collect events from Outlook on Mac using .olk15Event files"""
        try:
            import os
            from olk15_parser import OLK15EventParser

            logger.info(
                f"Collecting events from Outlook calendar (Mac): {source.get('name')}")

            # Skip if this calendar is not enabled
            if not source.get('enabled', True):
                logger.info(
                    f"Skipping disabled calendar: {source.get('name')}")
                return []

            # Find the Outlook Data directory
            outlook_data_dir = os.path.expanduser(
                "~/Library/Group Containers/UBF8T346G9.Office/Outlook/Outlook 15 Profiles/Main Profile/Data")
            
            if not os.path.exists(outlook_data_dir):
                logger.error(f"Outlook data directory not found: {outlook_data_dir}")
                return []

            # Initialize the OLK15 parser
            parser = OLK15EventParser(outlook_data_dir)
            
            # Check if we have a specific account directory to target
            account_email = source.get('account_email') or source.get('name', '')
            
            # Get all account directories
            accounts = parser.get_account_directories()
            logger.info(f"Found {len(accounts)} account directories")
            
            # If we have a specific account email, try to find matching directory
            target_accounts = []
            if '@' in account_email:
                for dir_num, account_info in accounts.items():
                    if account_info['email'] and account_email.lower() in account_info['email'].lower():
                        target_accounts.append((dir_num, account_info))
                        logger.info(f"Found matching account directory {dir_num} for {account_email}")
            
            # If no specific match or no email specified, use all enabled accounts
            if not target_accounts:
                target_accounts = [(dir_num, account_info) for dir_num, account_info in accounts.items()]
                logger.info(f"No specific account match, using all {len(target_accounts)} accounts")
            
            # Collect events from target accounts
            all_events = []
            for dir_num, account_info in target_accounts:
                try:
                    logger.info(f"Collecting events from account directory {dir_num}: {account_info['email']}")
                    
                    # Get events for this account
                    account_events = parser.get_events_for_account(account_info['path'])
                    
                    # Add source metadata to each event
                    for event in account_events:
                        event.update({
                            'source': 'outlook_mac',
                            'calendar_id': source.get('id', f'outlook-mac-{dir_num}'),
                            'calendar_name': source.get('name', f"Calendar ({account_info['email']})"),
                            'account_email': account_info['email'] or '',
                            'account_directory': dir_num
                        })
                    
                    all_events.extend(account_events)
                    logger.info(f"Collected {len(account_events)} events from directory {dir_num}")
                    
                except Exception as e:
                    logger.error(f"Error collecting events from directory {dir_num}: {e}")
                    continue

            logger.info(f"Total collected {len(all_events)} events from {len(target_accounts)} account directories")
            return all_events

        except ImportError as e:
            logger.error(f"Could not import OLK15EventParser: {e}")
            logger.error("Make sure olk15_parser.py is in the same directory as this script")
            return []
        except Exception as e:
            logger.error(f"Error collecting Outlook for Mac events using OLK15 parser: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []

    async def collect_outlook_events(self, source: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Collect events from Outlook, handling both Windows and Mac platforms"""
        try:
            import platform

            # Skip if this calendar is not enabled
            if not source.get('enabled', True):
                logger.info(
                    f"Skipping disabled calendar: {source.get('name')}")
                return []

            logger.info(
                f"Processing Outlook calendar: {source.get('name')} (ID: {source.get('id', 'N/A')})")

            if platform.system() == 'Windows':
                return await self._collect_outlook_windows_events(source)
            elif platform.system() == 'Darwin':  # macOS
                return await self._collect_outlook_mac_events(source)
            else:
                logger.warning(
                    f"Outlook integration is not supported on {platform.system()}")
                return []

        except Exception as e:
            logger.error(f"Error collecting Outlook events: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []

    async def collect_custom_events(self, source: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Collect events from a custom source"""
        try:
            # This is a placeholder for custom implementations
            logger.info(
                f"Would collect events from custom source: {source.get('name')}")

            # Custom sources could be anything:
            # - Database queries
            # - Web scraping
            # - Custom APIs
            # - Local files

            # For now, return empty list
            return []

        except Exception as e:
            logger.error(f"Error collecting custom events: {e}")
            return []

    async def process_pending_updates(self, updates: List[Dict[str, Any]]):
        """Process incoming updates from central service"""
        if not updates:
            return

        logger.info(
            f"Processing {len(updates)} pending updates from central service")

        for update in updates:
            try:
                update_type = update.get("type")
                update_data = update.get("data", {})

                if update_type == "calendar_metadata":
                    await self.apply_calendar_metadata_update(update_data)
                elif update_type == "sync_config":
                    await self.apply_sync_config_update(update_data)
                elif update_type == "event_update":
                    await self.apply_event_update(update_data)
                elif update_type == "calendar_create":
                    await self.apply_calendar_create(update_data)
                elif update_type == "calendar_delete":
                    await self.apply_calendar_delete(update_data)
                else:
                    logger.warning(f"Unknown update type: {update_type}")

                # Mark update as processed
                await self.mark_update_processed(update.get("id"))

            except Exception as e:
                logger.error(
                    f"Error processing update {update.get('id')}: {e}")

    async def apply_calendar_metadata_update(self, update_data: Dict[str, Any]):
        """Apply calendar metadata changes to local calendars"""
        try:
            calendar_id = update_data.get("calendar_id")
            provider = update_data.get("provider")
            metadata_changes = update_data.get("changes", {})

            logger.info(
                f"Applying metadata update to calendar {calendar_id} on {provider}")

            # Find the source configuration
            source = self.find_source_by_calendar_id(calendar_id, provider)
            if not source:
                logger.warning(f"Source not found for calendar {calendar_id}")
                return

            # Apply changes based on provider
            if provider == "google":
                await self.update_google_calendar_metadata(source, calendar_id, metadata_changes)
            elif provider == "microsoft":
                await self.update_microsoft_calendar_metadata(source, calendar_id, metadata_changes)
            elif provider == "exchange":
                await self.update_exchange_calendar_metadata(source, calendar_id, metadata_changes)
            elif provider == "outlook":
                await self.update_outlook_calendar_metadata(source, calendar_id, metadata_changes)
            else:
                logger.warning(
                    f"Unsupported provider for metadata update: {provider}")

        except Exception as e:
            logger.error(f"Error applying calendar metadata update: {e}")

    async def apply_sync_config_update(self, update_data: Dict[str, Any]):
        """Apply sync configuration changes"""
        try:
            config_changes = update_data.get("changes", {})

            logger.info("Applying sync configuration update")

            # Update local configuration
            for key, value in config_changes.items():
                if key in self.config:
                    old_value = self.config[key]
                    self.config[key] = value
                    logger.info(
                        f"Updated config {key}: {old_value} -> {value}")

            # Save updated configuration
            await self.save_config()

        except Exception as e:
            logger.error(f"Error applying sync config update: {e}")

    async def apply_event_update(self, update_data: Dict[str, Any]):
        """Apply event changes to local calendars"""
        try:
            event_data = update_data.get("event", {})
            # create, update, delete
            action = update_data.get("action", "update")

            logger.info(
                f"Applying event {action} for event {event_data.get('id')}")

            # Implementation would depend on the specific calendar provider
            # This is a placeholder for the actual implementation

        except Exception as e:
            logger.error(f"Error applying event update: {e}")

    async def apply_calendar_create(self, update_data: Dict[str, Any]):
        """Create a new calendar on the local provider"""
        try:
            calendar_data = update_data.get("calendar", {})
            provider = update_data.get("provider")

            logger.info(
                f"Creating new calendar on {provider}: {calendar_data.get('name')}")

            # Implementation would depend on the specific calendar provider
            # This is a placeholder for the actual implementation

        except Exception as e:
            logger.error(f"Error creating calendar: {e}")

    async def apply_calendar_delete(self, update_data: Dict[str, Any]):
        """Delete a calendar from the local provider"""
        try:
            calendar_id = update_data.get("calendar_id")
            provider = update_data.get("provider")

            logger.info(f"Deleting calendar {calendar_id} from {provider}")

            # Implementation would depend on the specific calendar provider
            # This is a placeholder for the actual implementation

        except Exception as e:
            logger.error(f"Error deleting calendar: {e}")

    def find_source_by_calendar_id(self, calendar_id: str, provider: str) -> Optional[Dict[str, Any]]:
        """Find source configuration by calendar ID and provider"""
        for source in self.config.get("calendar_sources", []):
            if (source.get("calendar_id") == calendar_id and
                    source.get("type") == provider):
                return source
        return None

    async def update_google_calendar_metadata(self, source: Dict[str, Any], calendar_id: str, changes: Dict[str, Any]):
        """Update Google Calendar metadata"""
        try:
            logger.info(
                f"Would update Google Calendar {calendar_id} with changes: {changes}")
            # Placeholder for Google Calendar API implementation
            # from googleapiclient.discovery import build
            # service = build('calendar', 'v3', credentials=credentials)
            # calendar_patch = {}
            # if 'name' in changes:
            #     calendar_patch['summary'] = changes['name']
            # if 'color' in changes:
            #     calendar_patch['backgroundColor'] = changes['color']
            # service.calendars().patch(calendarId=calendar_id, body=calendar_patch).execute()

        except Exception as e:
            logger.error(f"Error updating Google Calendar metadata: {e}")

    async def update_microsoft_calendar_metadata(self, source: Dict[str, Any], calendar_id: str, changes: Dict[str, Any]):
        """Update Microsoft Calendar metadata"""
        try:
            logger.info(
                f"Would update Microsoft Calendar {calendar_id} with changes: {changes}")
            # Placeholder for Microsoft Graph API implementation
            # from msgraph.core import GraphClient
            # graph_client = GraphClient(credentials=credentials)
            # patch_data = {}
            # if 'name' in changes:
            #     patch_data['name'] = changes['name']
            # if 'color' in changes:
            #     patch_data['color'] = changes['color']
            # await graph_client.patch(f'/me/calendars/{calendar_id}', data=patch_data)

        except Exception as e:
            logger.error(f"Error updating Microsoft Calendar metadata: {e}")

    async def update_exchange_calendar_metadata(self, source: Dict[str, Any], calendar_id: str, changes: Dict[str, Any]):
        """Update Exchange Calendar metadata"""
        try:
            logger.info(
                f"Would update Exchange Calendar {calendar_id} with changes: {changes}")
            # Placeholder for Exchange Web Services implementation
            # from exchangelib import Account, Calendar
            # account = Account(...)
            # calendar = account.calendar
            # if 'name' in changes:
            #     calendar.display_name = changes['name']
            # calendar.save()

        except Exception as e:
            logger.error(f"Error updating Exchange Calendar metadata: {e}")

    async def update_outlook_calendar_metadata(self, source: Dict[str, Any], calendar_id: str, changes: Dict[str, Any]):
        """Update Outlook Calendar metadata using COM interface"""
        try:
            logger.info(
                f"Would update Outlook Calendar {calendar_id} with changes: {changes}")

            # Placeholder for Outlook COM implementation
            # import win32com.client
            # outlook = win32com.client.Dispatch("Outlook.Application")
            # namespace = outlook.GetNamespace("MAPI")
            # calendar = namespace.GetDefaultFolder(9)  # olFolderCalendar
            # if 'name' in changes:
            #     calendar.Name = changes['name']

        except Exception as e:
            logger.error(f"Error updating Outlook Calendar metadata: {e}")

    async def mark_update_processed(self, update_id: str):
        """Mark an update as processed with the central service"""
        if not self.central_api_url or not self.agent_id or not update_id:
            return

        try:
            url = f"{self.central_api_url}/sync/agents/{self.agent_id}/updates/{update_id}/processed"
            async with self.http_session.post(url) as response:
                if response.status == 200:
                    logger.debug(f"Marked update {update_id} as processed")
                else:
                    logger.warning(
                        f"Failed to mark update {update_id} as processed: {response.status}")

        except Exception as e:
            logger.error(f"Error marking update as processed: {e}")

    async def get_pending_updates(self):
        """Manually check for pending updates from central service"""
        if not self.central_api_url or not self.agent_id:
            return []

        try:
            url = f"{self.central_api_url}/sync/agents/{self.agent_id}/pending-updates"
            async with self.http_session.get(url) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get("updates", [])
                else:
                    logger.warning(
                        f"Failed to get pending updates: {response.status}")
                    return []

        except Exception as e:
            logger.error(f"Error getting pending updates: {e}")
            return []

    async def run_sync_cycle(self):
        """Run a complete synchronization cycle"""
        try:
            logger.info("Starting sync cycle")

            # Collect events from all sources
            events = await self.collect_all_events()
            logger.info(f"Collected {len(events)} events from all sources")

            # Send events to central service via heartbeat
            result = await self.send_heartbeat(include_events=True)

            if result:
                logger.info(
                    f"Sync cycle completed: {result.get('message', 'Success')}")
            else:
                logger.warning(
                    "Sync cycle completed but no result from central service")

            return True

        except Exception as e:
            logger.error(f"Error in sync cycle: {e}")
            return False

    async def run(self):
        """Run the agent in continuous mode"""
        try:
            self.running = True
            logger.info(
                f"Agent started. Sync interval: {self.sync_interval} minutes")

            while self.running:
                # Run a sync cycle
                await self.run_sync_cycle()

                # Send a simple heartbeat
                await self.send_heartbeat(include_events=False)

                # Wait for next cycle
                logger.info(
                    f"Waiting {self.sync_interval} minutes until next sync")
                await asyncio.sleep(self.sync_interval * 60)

        except asyncio.CancelledError:
            logger.info("Agent stopping due to cancellation")
            self.running = False

        except Exception as e:
            logger.error(f"Error in agent run loop: {e}")
            self.running = False

        finally:
            # Clean up
            if self.http_session:
                await self.http_session.close()

            logger.info("Agent stopped")

    async def stop(self):
        """Stop the agent"""
        self.running = False
        logger.info("Agent stopping")

        # Clean up
        if self.http_session:
            await self.http_session.close()


async def main():
    """Main function for running the agent"""
    parser = argparse.ArgumentParser(
        description="Remote Calendar Synchronization Agent")
    parser.add_argument("--config", default="agent_config.json",
                        help="Path to configuration file")
    parser.add_argument("--central-api", default=None,
                        help="URL of central calendar service API")
    parser.add_argument("--once", action="store_true",
                        help="Run sync once and exit")
    parser.add_argument("--interval", type=int, default=None,
                        help="Sync interval in minutes")

    args = parser.parse_args()

    try:
        # Create and initialize agent
        agent = RemoteCalendarAgent(
            config_path=args.config, central_api_url=args.central_api)
        await agent.initialize()

        # Override sync interval if specified
        if args.interval:
            agent.sync_interval = args.interval
            agent.config["sync_interval_minutes"] = args.interval
            await agent.save_config()

        if args.once:
            # Run one sync cycle and exit
            await agent.run_sync_cycle()
        else:
            # Run continuously
            await agent.run()

    except KeyboardInterrupt:
        logger.info("Agent interrupted by user")

    except Exception as e:
        logger.error(f"Unhandled error: {e}")
        return 1

    return 0

if __name__ == "__main__":
    asyncio.run(main())

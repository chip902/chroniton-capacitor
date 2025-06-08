"""
Enhanced Remote Calendar Synchronization Agent

This version includes working Outlook integration for Windows.
"""

import os
import json
import asyncio
import logging
import argparse
import aiohttp
import uuid
from datetime import datetime, timedelta
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


class EnhancedRemoteCalendarAgent:
    """
    Enhanced agent for synchronizing calendars from isolated environments
    """

    def __init__(self, config_path: str):
        """Initialize the calendar agent"""
        self.config_path = config_path
        self.config = None
        self.agent_id = None
        self.agent_name = None
        self.central_api_url = None
        self.environment = platform.node()
        self.running = False
        self.sync_interval = 60
        self.http_session = None
        self.sync_tokens = {}

    async def initialize(self):
        """Initialize the agent"""
        await self.load_config()
        self.http_session = aiohttp.ClientSession()
        await self.register_with_central_service()

    async def load_config(self):
        """Load agent configuration from file"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r") as f:
                    self.config = json.load(f)

                self.agent_id = self.config.get("agent_id")
                self.agent_name = self.config.get(
                    "agent_name", f"Agent-{socket.gethostname()}")
                self.environment = self.config.get(
                    "environment", self.environment)
                self.central_api_url = self.config.get("central_api_url")
                self.sync_interval = self.config.get(
                    "sync_interval_minutes", 15)
                self.sync_tokens = self.config.get("sync_tokens", {})

                logger.info(f"Configuration loaded: Agent ID: {self.agent_id}")
            else:
                raise FileNotFoundError(
                    f"Configuration file not found: {self.config_path}")

        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            raise

    async def save_config(self):
        """Save agent configuration to file"""
        try:
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
            return

        try:
            agent_data = {
                "id": self.agent_id,
                "name": self.agent_name,
                "environment": self.environment,
                "agent_type": "python",
                "communication_method": "api",
                "interval_minutes": self.sync_interval,
                "sources": []
            }

            url = f"{self.central_api_url}/sync/agents"
            async with self.http_session.post(url, json=agent_data) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info(
                        f"Agent registered successfully with ID: {self.agent_id}")
                else:
                    error_text = await response.text()
                    logger.warning(
                        f"Registration failed: {response.status} - {error_text}")

        except Exception as e:
            logger.error(f"Error registering with central service: {e}")

    async def collect_outlook_events(self, source: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Collect events from Outlook on Windows using COM interface"""
        if not source.get('enabled', True):
            logger.info(f"Skipping disabled calendar: {source.get('name')}")
            return []

        try:
            import win32com.client
            import pythoncom
            import pywintypes

            logger.info(
                f"Collecting events from Outlook calendar: {source.get('name')}")

            # Initialize COM for this thread
            pythoncom.CoInitialize()

            try:
                # Connect to Outlook
                outlook = win32com.client.Dispatch("Outlook.Application")
                namespace = outlook.GetNamespace("MAPI")

                # Get the calendar folder
                calendar_name = source.get("calendar_name", "Calendar")
                calendar = None

                # Try to find the calendar by name or use default
                try:
                    if calendar_name == "Calendar":
                        calendar = namespace.GetDefaultFolder(
                            9)  # olFolderCalendar
                    else:
                        # Search for named calendar
                        default_calendar = namespace.GetDefaultFolder(9)
                        for folder in default_calendar.Folders:
                            if folder.Name == calendar_name:
                                calendar = folder
                                break

                        if not calendar:
                            logger.warning(
                                f"Calendar '{calendar_name}' not found. Using default calendar.")
                            calendar = default_calendar
                except Exception as e:
                    logger.error(f"Error accessing calendar: {e}")
                    # Fallback to default calendar
                    calendar = namespace.GetDefaultFolder(9)

                # Get appointments from the last 7 days and next 30 days
                start_date = (datetime.now() - timedelta(days=7)
                              ).strftime('%m/%d/%Y')
                end_date = (datetime.now() + timedelta(days=30)
                            ).strftime('%m/%d/%Y')

                # Create filter for appointments
                filter_str = f"[Start] >= '{start_date}' AND [End] <= '{end_date}'"

                try:
                    appointments = calendar.Items
                    appointments.IncludeRecurrences = True
                    appointments.Sort("[Start]")
                    restricted_appointments = appointments.Restrict(filter_str)
                except Exception as e:
                    logger.error(f"Error filtering appointments: {e}")
                    return []

                events = []
                processed_count = 0

                for appointment in restricted_appointments:
                    try:
                        # Basic event data
                        event_id = getattr(
                            appointment, 'EntryID', str(uuid.uuid4()))
                        subject = getattr(appointment, 'Subject', 'No Title')
                        start_time = getattr(appointment, 'Start', None)
                        end_time = getattr(appointment, 'End', None)

                        if not start_time or not end_time:
                            logger.warning(
                                f"Skipping appointment without start/end time: {subject}")
                            continue

                        # Convert COM datetime to ISO format
                        start_iso = start_time.strftime('%Y-%m-%dT%H:%M:%S')
                        end_iso = end_time.strftime('%Y-%m-%dT%H:%M:%S')

                        event = {
                            "id": f"outlook_{event_id}",
                            "provider": "outlook",
                            "provider_id": event_id,
                            "title": subject,
                            "description": getattr(appointment, 'Body', ''),
                            "location": getattr(appointment, 'Location', ''),
                            "start_time": start_iso,
                            "end_time": end_iso,
                            "all_day": getattr(appointment, 'AllDayEvent', False),
                            "recurring": getattr(appointment, 'IsRecurring', False),
                            "calendar_id": source.get("name", "Calendar"),
                            "calendar_name": calendar_name,
                            "status": "confirmed",
                            "private": getattr(appointment, 'Sensitivity', 0) > 0,
                            "created_at": getattr(appointment, 'CreationTime', datetime.now()).strftime('%Y-%m-%dT%H:%M:%S'),
                            "updated_at": getattr(appointment, 'LastModificationTime', datetime.now()).strftime('%Y-%m-%dT%H:%M:%S'),
                            "organizer": {
                                "email": getattr(appointment, 'Organizer', ''),
                                "name": getattr(appointment, 'Organizer', '')
                            },
                            "participants": []
                        }

                        # Add attendees if available
                        try:
                            if hasattr(appointment, "Recipients") and appointment.Recipients:
                                for recipient in appointment.Recipients:
                                    participant = {
                                        "email": getattr(recipient, 'Address', ''),
                                        "name": getattr(recipient, 'Name', ''),
                                        "response_status": "accepted"  # Default status
                                    }
                                    event["participants"].append(participant)
                        except Exception as e:
                            logger.debug(f"Could not extract attendees: {e}")

                        events.append(event)
                        processed_count += 1

                        # Limit to prevent overwhelming the system
                        if processed_count >= 200:
                            logger.info(
                                "Reached maximum event limit (200), stopping collection")
                            break

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
                pythoncom.CoUninitialize()

        except ImportError:
            logger.error(
                "win32com package not available - required for Outlook integration on Windows")
            logger.error("Install with: pip install pywin32")
            return []
        except Exception as e:
            logger.error(f"Unexpected error in Outlook collection: {e}")
            return []

    async def collect_all_events(self) -> List[Dict[str, Any]]:
        """Collect events from all configured calendar sources"""
        all_events = []

        for source in self.config.get("calendar_sources", []):
            try:
                source_type = source.get("type")

                if source_type == "outlook":
                    events = await self.collect_outlook_events(source)
                    all_events.extend(events)
                    source["last_sync"] = datetime.utcnow().isoformat()
                else:
                    logger.warning(f"Unknown source type: {source_type}")

            except Exception as e:
                logger.error(
                    f"Error collecting events from source {source.get('name', 'unknown')}: {e}")

        await self.save_config()
        return all_events

    async def send_events_to_central_service(self, events: List[Dict[str, Any]]) -> bool:
        """Send collected events to the central service"""
        if not self.central_api_url or not events:
            return False

        try:
            # Send events via import endpoint
            url = f"{self.central_api_url}/sync/import/{self.agent_id}"
            async with self.http_session.post(url, json=events) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info(
                        f"Successfully sent {len(events)} events to central service")
                    logger.info(f"Import result: {result}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(
                        f"Failed to send events: {response.status} - {error_text}")
                    return False

        except Exception as e:
            logger.error(f"Error sending events to central service: {e}")
            return False

    async def send_heartbeat(self) -> Dict[str, Any]:
        """Send heartbeat to central service"""
        if not self.central_api_url or not self.agent_id:
            return {}

        try:
            heartbeat_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "status": "active",
                "environment": self.environment,
                "last_event_count": len(await self.collect_all_events()) if hasattr(self, '_last_events') else 0
            }

            url = f"{self.central_api_url}/sync/agents/{self.agent_id}/heartbeat"
            async with self.http_session.post(url, json=heartbeat_data) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info("Heartbeat sent successfully")
                    return result
                else:
                    error_text = await response.text()
                    logger.error(
                        f"Failed to send heartbeat: {response.status} - {error_text}")
                    return {}

        except Exception as e:
            logger.error(f"Error sending heartbeat: {e}")
            return {}

    async def run_sync_cycle(self):
        """Run a complete synchronization cycle"""
        try:
            logger.info("Starting sync cycle")

            # Collect events from all sources
            events = await self.collect_all_events()
            logger.info(f"Collected {len(events)} events from all sources")

            if events:
                # Send events to central service
                success = await self.send_events_to_central_service(events)
                if success:
                    logger.info("Sync cycle completed successfully")
                else:
                    logger.warning(
                        "Sync cycle completed but event upload failed")
            else:
                logger.info("No events to sync")

            # Send heartbeat
            await self.send_heartbeat()

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
                await self.run_sync_cycle()

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
            if self.http_session:
                await self.http_session.close()
            logger.info("Agent stopped")

    async def stop(self):
        """Stop the agent"""
        self.running = False
        if self.http_session:
            await self.http_session.close()


async def main():
    """Main function for running the agent"""
    parser = argparse.ArgumentParser(
        description="Enhanced Remote Calendar Synchronization Agent")
    parser.add_argument("--config", default="outlook_config.json",
                        help="Path to configuration file")
    parser.add_argument("--once", action="store_true",
                        help="Run sync once and exit")

    args = parser.parse_args()

    try:
        agent = EnhancedRemoteCalendarAgent(config_path=args.config)
        await agent.initialize()

        if args.once:
            await agent.run_sync_cycle()
        else:
            await agent.run()

    except KeyboardInterrupt:
        logger.info("Agent interrupted by user")
    except Exception as e:
        logger.error(f"Unhandled error: {e}")
        return 1

    return 0

if __name__ == "__main__":
    asyncio.run(main())

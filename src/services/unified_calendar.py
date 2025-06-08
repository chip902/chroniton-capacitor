import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from services.google_calendar import GoogleCalendarService
from services.microsoft_calendar import MicrosoftCalendarService
from services.apple_calendar import AppleCalendarService
from services.exchange_calendar import ExchangeCalendarService
from services.calendar_event import CalendarEvent, CalendarProvider

# Set up logging
logger = logging.getLogger(__name__)


class UnifiedCalendarService:
    """
    Unified service to fetch events from multiple calendar providers
    """

    def __init__(self):
        """Initialize the unified calendar service"""
        self.google_service = GoogleCalendarService()
        self.microsoft_service = MicrosoftCalendarService()
        self.apple_service = AppleCalendarService()
        self.exchange_service = ExchangeCalendarService()

    async def list_all_calendars(self, user_credentials: Dict[str, Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        List calendars from all providers the user is authenticated with

        Args:
            user_credentials: Dictionary mapping provider names to credentials

        Returns:
            Dictionary mapping provider names to list of calendars
        """
        results = {}
        tasks = []

        # Google calendars
        if CalendarProvider.GOOGLE.value in user_credentials:
            google_creds = user_credentials[CalendarProvider.GOOGLE.value]
            tasks.append(self._get_google_calendars(google_creds))

        # Microsoft calendars
        if CalendarProvider.MICROSOFT.value in user_credentials:
            microsoft_creds = user_credentials[CalendarProvider.MICROSOFT.value]
            tasks.append(self._get_microsoft_calendars(microsoft_creds))

        # Apple calendars
        if CalendarProvider.APPLE.value in user_credentials:
            apple_creds = user_credentials[CalendarProvider.APPLE.value]
            tasks.append(self._get_apple_calendars(apple_creds))

        # Exchange/Mailcow calendars
        if CalendarProvider.EXCHANGE.value in user_credentials:
            exchange_creds = user_credentials[CalendarProvider.EXCHANGE.value]
            tasks.append(self._get_exchange_calendars(exchange_creds))

        # Execute tasks concurrently
        if tasks:
            provider_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for result in provider_results:
                if isinstance(result, Exception):
                    logger.error(f"Error fetching calendars: {result}")
                    continue

                # Add calendars to results
                provider, calendars = result
                results[provider] = calendars

        return results

    async def _get_google_calendars(self, credentials: Dict[str, Any]) -> tuple:
        """Helper method to fetch Google calendars"""
        try:
            calendars = await self.google_service.list_calendars(credentials)
            return CalendarProvider.GOOGLE.value, calendars
        except Exception as e:
            logger.error(f"Error fetching Google calendars: {e}")
            return CalendarProvider.GOOGLE.value, []

    async def _get_microsoft_calendars(self, credentials: Dict[str, Any]) -> tuple:
        """Helper method to fetch Microsoft calendars"""
        try:
            calendars = await self.microsoft_service.list_calendars(credentials)
            return CalendarProvider.MICROSOFT.value, calendars
        except Exception as e:
            logger.error(f"Error fetching Microsoft calendars: {e}")
            return CalendarProvider.MICROSOFT.value, []

    async def _get_apple_calendars(self, credentials: Dict[str, Any]) -> tuple:
        """Helper method to fetch Apple calendars"""
        try:
            calendars = await self.apple_service.list_calendars(credentials)
            return CalendarProvider.APPLE.value, calendars
        except Exception as e:
            logger.error(f"Error fetching Apple calendars: {e}")
            return CalendarProvider.APPLE.value, []

    async def _get_exchange_calendars(self, credentials: Dict[str, Any]) -> tuple:
        """Helper method to fetch Exchange/Mailcow calendars"""
        try:
            # First authenticate with the Exchange server
            auth_info = await self.exchange_service.authenticate(credentials)

            # Then list the calendars
            calendars = await self.exchange_service.list_calendars(auth_info)
            return CalendarProvider.EXCHANGE.value, calendars
        except Exception as e:
            logger.error(f"Error fetching Exchange calendars: {e}")
            return CalendarProvider.EXCHANGE.value, []

    async def get_all_events(
        self,
        user_credentials: Dict[str, Dict[str, Any]],
        calendar_selections: Dict[str, List[str]],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        max_results_per_calendar: int = 100,
        sync_tokens: Optional[Dict[str, Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Get events from multiple calendars across providers

        Args:
            user_credentials: Dict mapping provider names to credentials
            calendar_selections: Dict mapping provider names to list of calendar IDs
            start_date: Start date for events (defaults to today)
            end_date: End date for events (defaults to 30 days from start)
            max_results_per_calendar: Maximum events per calendar
            sync_tokens: Dict of sync tokens for incremental sync

        Returns:
            Dict with normalized events and new sync tokens
        """
        # Set default dates if not provided
        if not start_date:
            start_date = datetime.utcnow().replace(
                hour=0, minute=0, second=0, microsecond=0)

        if not end_date:
            end_date = start_date + timedelta(days=30)

        # Initialize sync tokens if not provided
        if not sync_tokens:
            sync_tokens = {
                CalendarProvider.GOOGLE.value: {},
                CalendarProvider.MICROSOFT.value: {},
                CalendarProvider.APPLE.value: {},
                CalendarProvider.EXCHANGE.value: {}
            }

        # Create tasks for fetching events
        tasks = []

        # Google events
        if (CalendarProvider.GOOGLE.value in user_credentials and
                CalendarProvider.GOOGLE.value in calendar_selections):

            google_creds = user_credentials[CalendarProvider.GOOGLE.value]
            google_calendars = calendar_selections[CalendarProvider.GOOGLE.value]

            google_tokens = sync_tokens.get(CalendarProvider.GOOGLE.value, {})

            for calendar_id in google_calendars:
                sync_token = google_tokens.get(calendar_id)
                tasks.append(
                    self._get_google_events(
                        google_creds,
                        calendar_id,
                        start_date,
                        end_date,
                        max_results_per_calendar,
                        sync_token
                    )
                )

        # Microsoft events
        if (CalendarProvider.MICROSOFT.value in user_credentials and
                CalendarProvider.MICROSOFT.value in calendar_selections):

            microsoft_creds = user_credentials[CalendarProvider.MICROSOFT.value]
            microsoft_calendars = calendar_selections[CalendarProvider.MICROSOFT.value]

            microsoft_tokens = sync_tokens.get(
                CalendarProvider.MICROSOFT.value, {})

            for calendar_id in microsoft_calendars:
                delta_link = microsoft_tokens.get(calendar_id)
                tasks.append(
                    self._get_microsoft_events(
                        microsoft_creds,
                        calendar_id,
                        start_date,
                        end_date,
                        max_results_per_calendar,
                        delta_link
                    )
                )

        # Apple events
        if (CalendarProvider.APPLE.value in user_credentials and
                CalendarProvider.APPLE.value in calendar_selections):

            apple_creds = user_credentials[CalendarProvider.APPLE.value]
            apple_calendars = calendar_selections[CalendarProvider.APPLE.value]

            apple_tokens = sync_tokens.get(CalendarProvider.APPLE.value, {})

            for calendar_id in apple_calendars:
                delta_link = apple_tokens.get(calendar_id)
                tasks.append(
                    self._get_apple_events(
                        apple_creds,
                        calendar_id,
                        start_date,
                        end_date,
                        max_results_per_calendar,
                        delta_link
                    )
                )

        # Exchange/Mailcow events
        if (CalendarProvider.EXCHANGE.value in user_credentials and
                CalendarProvider.EXCHANGE.value in calendar_selections):

            exchange_creds = user_credentials[CalendarProvider.EXCHANGE.value]
            exchange_calendars = calendar_selections[CalendarProvider.EXCHANGE.value]

            exchange_tokens = sync_tokens.get(
                CalendarProvider.EXCHANGE.value, {})

            # First authenticate with the Exchange server
            try:
                auth_info = await self.exchange_service.authenticate(exchange_creds)

                for calendar_id in exchange_calendars:
                    sync_token = exchange_tokens.get(calendar_id)
                    tasks.append(
                        self._get_exchange_events(
                            auth_info,
                            calendar_id,
                            start_date,
                            end_date,
                            max_results_per_calendar,
                            sync_token
                        )
                    )
            except Exception as e:
                logger.error(f"Error authenticating with Exchange server: {e}")

        # Execute all tasks concurrently
        all_events = []
        new_sync_tokens = {
            CalendarProvider.GOOGLE.value: {},
            CalendarProvider.MICROSOFT.value: {},
            CalendarProvider.APPLE.value: {},
            CalendarProvider.EXCHANGE.value: {}
        }

        if tasks:
            # Gather results from all tasks
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Error fetching events: {result}")
                    continue

                # Extract events and sync tokens
                provider, calendar_id, events, sync_token = result

                # Add events to the combined list
                all_events.extend(events)

                # Update sync tokens
                if sync_token:
                    new_sync_tokens[provider][calendar_id] = sync_token

        # Sort events by start time
        all_events.sort(key=lambda e: e.start_time)

        return {
            "events": all_events,
            "syncTokens": new_sync_tokens
        }

    async def _get_google_events(
        self,
        credentials: Dict[str, Any],
        calendar_id: str,
        start_date: datetime,
        end_date: datetime,
        max_results: int,
        sync_token: Optional[str]
    ) -> tuple:
        """Helper method to fetch Google events"""
        try:
            result = await self.google_service.get_events(
                token_info=credentials,
                calendar_id=calendar_id,
                start_date=start_date,
                end_date=end_date,
                max_results=max_results,
                sync_token=sync_token
            )

            return (
                CalendarProvider.GOOGLE.value,
                calendar_id,
                result.get('events', []),
                result.get('nextSyncToken')
            )
        except Exception as e:
            logger.error(
                f"Error fetching Google events for calendar {calendar_id}: {e}")
            return CalendarProvider.GOOGLE.value, calendar_id, [], None

    async def _get_microsoft_events(
        self,
        credentials: Dict[str, Any],
        calendar_id: str,
        start_date: datetime,
        end_date: datetime,
        max_results: int,
        delta_link: Optional[str]
    ) -> tuple:
        """Helper method to fetch Microsoft events"""
        try:
            result = await self.microsoft_service.get_events(
                token_info=credentials,
                calendar_id=calendar_id,
                start_date=start_date,
                end_date=end_date,
                max_results=max_results,
                delta_link=delta_link
            )

            return (
                CalendarProvider.MICROSOFT.value,
                calendar_id,
                result.get('events', []),
                result.get('deltaLink')
            )
        except Exception as e:
            logger.error(
                f"Error fetching Microsoft events for calendar {calendar_id}: {e}")
            return CalendarProvider.MICROSOFT.value, calendar_id, [], None

    async def _get_apple_events(
        self,
        credentials: Dict[str, Any],
        calendar_id: str,
        start_date: datetime,
        end_date: datetime,
        max_results: int,
        delta_link: Optional[str]
    ) -> tuple:
        """Helper method to fetch Apple events"""
        try:
            result = await self.apple_service.get_events(
                token_info=credentials,
                calendar_id=calendar_id,
                start_date=start_date,
                end_date=end_date,
                max_results=max_results,
                delta_link=delta_link
            )

            return (
                CalendarProvider.APPLE.value,
                calendar_id,
                result.get('events', []),
                result.get('deltaLink')
            )
        except Exception as e:
            logger.error(
                f"Error fetching Apple events for calendar {calendar_id}: {e}")
            return CalendarProvider.APPLE.value, calendar_id, [], None

    async def _get_exchange_events(
        self,
        auth_info: Dict[str, Any],
        calendar_id: str,
        start_date: datetime,
        end_date: datetime,
        max_results: int,
        sync_token: Optional[str]
    ) -> tuple:
        """Helper method to fetch Exchange/Mailcow events"""
        try:
            result = await self.exchange_service.get_events(
                auth_info=auth_info,
                calendar_id=calendar_id,
                start_date=start_date,
                end_date=end_date,
                max_results=max_results,
                sync_token=sync_token
            )

            return (
                CalendarProvider.EXCHANGE.value,
                calendar_id,
                result.get('events', []),
                result.get('syncToken')
            )
        except Exception as e:
            logger.error(
                f"Error fetching Exchange events for calendar {calendar_id}: {e}")
            return CalendarProvider.EXCHANGE.value, calendar_id, [], None

    async def update_calendar_metadata(
        self,
        provider: str,
        calendar_id: str,
        credentials: Dict[str, Any],
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update calendar metadata like name, color, description"""
        try:
            if provider == CalendarProvider.GOOGLE.value:
                return await self.google_service.update_calendar_metadata(
                    credentials, calendar_id, updates
                )
            elif provider == CalendarProvider.MICROSOFT.value:
                return await self.microsoft_service.update_calendar_metadata(
                    credentials, calendar_id, updates
                )
            elif provider == CalendarProvider.APPLE.value:
                return await self.apple_service.update_calendar_metadata(
                    credentials, calendar_id, updates
                )
            elif provider == CalendarProvider.EXCHANGE.value:
                auth_info = await self.exchange_service.authenticate(credentials)
                return await self.exchange_service.update_calendar_metadata(
                    auth_info, calendar_id, updates
                )
            else:
                raise ValueError(f"Unsupported provider: {provider}")

        except Exception as e:
            logger.error(
                f"Error updating calendar metadata for {provider}: {e}")
            raise

    async def create_calendar(
        self,
        provider: str,
        credentials: Dict[str, Any],
        calendar_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new calendar"""
        try:
            if provider == CalendarProvider.GOOGLE.value:
                return await self.google_service.create_calendar(
                    credentials, calendar_data
                )
            elif provider == CalendarProvider.MICROSOFT.value:
                return await self.microsoft_service.create_calendar(
                    credentials, calendar_data
                )
            elif provider == CalendarProvider.APPLE.value:
                return await self.apple_service.create_calendar(
                    credentials, calendar_data
                )
            elif provider == CalendarProvider.EXCHANGE.value:
                auth_info = await self.exchange_service.authenticate(credentials)
                return await self.exchange_service.create_calendar(
                    auth_info, calendar_data
                )
            else:
                raise ValueError(f"Unsupported provider: {provider}")

        except Exception as e:
            logger.error(f"Error creating calendar for {provider}: {e}")
            raise

    async def delete_calendar(
        self,
        provider: str,
        calendar_id: str,
        credentials: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Delete a calendar"""
        try:
            if provider == CalendarProvider.GOOGLE.value:
                return await self.google_service.delete_calendar(
                    credentials, calendar_id
                )
            elif provider == CalendarProvider.MICROSOFT.value:
                return await self.microsoft_service.delete_calendar(
                    credentials, calendar_id
                )
            elif provider == CalendarProvider.APPLE.value:
                return await self.apple_service.delete_calendar(
                    credentials, calendar_id
                )
            elif provider == CalendarProvider.EXCHANGE.value:
                auth_info = await self.exchange_service.authenticate(credentials)
                return await self.exchange_service.delete_calendar(
                    auth_info, calendar_id
                )
            else:
                raise ValueError(f"Unsupported provider: {provider}")

        except Exception as e:
            logger.error(f"Error deleting calendar for {provider}: {e}")
            raise

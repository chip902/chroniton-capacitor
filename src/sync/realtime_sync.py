"""
Real-time Calendar Synchronization Engine

This module implements real-time synchronization capabilities including webhook
receivers for push notifications, intelligent polling schedulers, and WebSocket
support for frontend real-time updates.
"""

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Set, Callable, Any
import json
import hashlib
from uuid import uuid4

from fastapi import FastAPI, Request, HTTPException, WebSocket, BackgroundTasks
from fastapi.routing import APIRouter
import aiohttp

from services.calendar_event import CalendarEvent, CalendarProvider
from services.unified_calendar import UnifiedCalendarService
from sync.architecture import SyncConfiguration, SyncSource
from sync.sync_engine import BidirectionalSyncEngine
from sync.storage import SyncStorageManager

logger = logging.getLogger(__name__)


class ChangeType(str, Enum):
    """Types of calendar changes"""
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    METADATA_CHANGED = "metadata_changed"


class NotificationPriority(str, Enum):
    """Priority levels for real-time notifications"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class ChangeNotification:
    """Represents a calendar change notification"""
    id: str
    source: str  # "webhook", "polling", "agent"
    provider: CalendarProvider
    calendar_id: str
    change_type: ChangeType
    event_id: Optional[str]
    timestamp: datetime
    priority: NotificationPriority = NotificationPriority.NORMAL
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Webhook-specific fields
    webhook_id: Optional[str] = None
    resource_id: Optional[str] = None
    
    # Polling-specific fields
    sync_token: Optional[str] = None
    next_sync_token: Optional[str] = None


@dataclass
class PollingSchedule:
    """Configuration for polling-based sync"""
    source_id: str
    provider: CalendarProvider
    calendar_ids: List[str]
    interval_minutes: int
    last_poll: Optional[datetime] = None
    next_poll: Optional[datetime] = None
    consecutive_failures: int = 0
    is_active: bool = True
    backoff_multiplier: float = 1.0
    
    def calculate_next_poll(self) -> datetime:
        """Calculate next poll time with exponential backoff for failures"""
        base_interval = self.interval_minutes * self.backoff_multiplier
        
        # Apply exponential backoff for failures
        if self.consecutive_failures > 0:
            backoff_minutes = min(base_interval * (2 ** self.consecutive_failures), 240)  # Max 4 hours
        else:
            backoff_minutes = base_interval
        
        next_poll = datetime.utcnow() + timedelta(minutes=backoff_minutes)
        self.next_poll = next_poll
        return next_poll


class WebSocketManager:
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_subscriptions: Dict[str, Set[str]] = defaultdict(set)
    
    async def connect(self, websocket: WebSocket, client_id: str):
        """Accept and register a new WebSocket connection"""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.connection_subscriptions[client_id] = set()
        logger.info(f"WebSocket client {client_id} connected")
    
    def disconnect(self, client_id: str):
        """Remove a WebSocket connection"""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.connection_subscriptions:
            del self.connection_subscriptions[client_id]
        logger.info(f"WebSocket client {client_id} disconnected")
    
    def subscribe(self, client_id: str, calendar_id: str):
        """Subscribe a client to calendar updates"""
        if client_id in self.connection_subscriptions:
            self.connection_subscriptions[client_id].add(calendar_id)
            logger.debug(f"Client {client_id} subscribed to calendar {calendar_id}")
    
    def unsubscribe(self, client_id: str, calendar_id: str):
        """Unsubscribe a client from calendar updates"""
        if client_id in self.connection_subscriptions:
            self.connection_subscriptions[client_id].discard(calendar_id)
            logger.debug(f"Client {client_id} unsubscribed from calendar {calendar_id}")
    
    async def broadcast_to_subscribers(self, calendar_id: str, message: Dict[str, Any]):
        """Broadcast a message to all subscribers of a calendar"""
        disconnected_clients = []
        
        for client_id, subscriptions in self.connection_subscriptions.items():
            if calendar_id in subscriptions:
                websocket = self.active_connections.get(client_id)
                if websocket:
                    try:
                        await websocket.send_json(message)
                        logger.debug(f"Sent update to client {client_id}")
                    except Exception as e:
                        logger.warning(f"Failed to send to client {client_id}: {e}")
                        disconnected_clients.append(client_id)
        
        # Clean up disconnected clients
        for client_id in disconnected_clients:
            self.disconnect(client_id)
    
    async def send_to_client(self, client_id: str, message: Dict[str, Any]):
        """Send a message to a specific client"""
        websocket = self.active_connections.get(client_id)
        if websocket:
            try:
                await websocket.send_json(message)
                return True
            except Exception as e:
                logger.warning(f"Failed to send to client {client_id}: {e}")
                self.disconnect(client_id)
                return False
        return False


class WebhookReceiver:
    """Handles incoming webhooks from calendar providers"""
    
    def __init__(self, realtime_engine: 'RealtimeSyncEngine'):
        self.engine = realtime_engine
        self.webhook_secrets: Dict[str, str] = {}
        self.router = APIRouter(prefix="/webhooks", tags=["webhooks"])
        self._setup_routes()
    
    def _setup_routes(self):
        """Set up webhook endpoint routes"""
        self.router.post("/google/{webhook_id}")(self.handle_google_webhook)
        self.router.post("/microsoft/{webhook_id}")(self.handle_microsoft_webhook)
        self.router.get("/google/{webhook_id}")(self.verify_google_webhook)
    
    async def handle_google_webhook(self, webhook_id: str, request: Request):
        """Handle Google Calendar push notifications"""
        try:
            # Verify webhook authenticity
            headers = dict(request.headers)
            if not self._verify_google_webhook(headers, webhook_id):
                raise HTTPException(status_code=401, detail="Invalid webhook signature")
            
            # Parse webhook data
            channel_id = headers.get('x-goog-channel-id')
            resource_id = headers.get('x-goog-resource-id')
            resource_state = headers.get('x-goog-resource-state')
            
            if resource_state in ['exists', 'sync']:
                # Create change notification
                notification = ChangeNotification(
                    id=str(uuid4()),
                    source="webhook",
                    provider=CalendarProvider.GOOGLE,
                    calendar_id=channel_id or "unknown",
                    change_type=ChangeType.UPDATED,  # Google doesn't specify exact change type
                    event_id=None,
                    timestamp=datetime.utcnow(),
                    priority=NotificationPriority.HIGH,
                    webhook_id=webhook_id,
                    resource_id=resource_id,
                    metadata={
                        'resource_state': resource_state,
                        'channel_id': channel_id
                    }
                )
                
                # Process the change
                await self.engine.process_change_notification(notification)
            
            return {"status": "ok"}
        
        except Exception as e:
            logger.error(f"Error handling Google webhook: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def verify_google_webhook(self, webhook_id: str, request: Request):
        """Handle Google webhook verification"""
        challenge = request.query_params.get('hub.challenge')
        if challenge:
            return challenge
        return {"status": "ok"}
    
    async def handle_microsoft_webhook(self, webhook_id: str, request: Request):
        """Handle Microsoft Graph change notifications"""
        try:
            # Verify webhook authenticity
            headers = dict(request.headers)
            if not self._verify_microsoft_webhook(headers, webhook_id):
                raise HTTPException(status_code=401, detail="Invalid webhook signature")
            
            # Parse webhook payload
            body = await request.json()
            
            for notification_data in body.get('value', []):
                # Extract change information
                change_type_map = {
                    'created': ChangeType.CREATED,
                    'updated': ChangeType.UPDATED,
                    'deleted': ChangeType.DELETED
                }
                
                change_type = change_type_map.get(
                    notification_data.get('changeType'), 
                    ChangeType.UPDATED
                )
                
                resource = notification_data.get('resource', '')
                calendar_id = self._extract_calendar_id_from_resource(resource)
                event_id = self._extract_event_id_from_resource(resource)
                
                notification = ChangeNotification(
                    id=str(uuid4()),
                    source="webhook",
                    provider=CalendarProvider.MICROSOFT,
                    calendar_id=calendar_id,
                    change_type=change_type,
                    event_id=event_id,
                    timestamp=datetime.utcnow(),
                    priority=NotificationPriority.HIGH,
                    webhook_id=webhook_id,
                    resource_id=notification_data.get('resourceData', {}).get('id'),
                    metadata=notification_data
                )
                
                # Process the change
                await self.engine.process_change_notification(notification)
            
            return {"status": "ok"}
        
        except Exception as e:
            logger.error(f"Error handling Microsoft webhook: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    def _verify_google_webhook(self, headers: Dict[str, str], webhook_id: str) -> bool:
        """Verify Google webhook authenticity"""
        # For production, implement proper signature verification
        # This is a simplified version
        return True
    
    def _verify_microsoft_webhook(self, headers: Dict[str, str], webhook_id: str) -> bool:
        """Verify Microsoft webhook authenticity"""
        # For production, implement proper signature verification
        # This is a simplified version
        return True
    
    def _extract_calendar_id_from_resource(self, resource: str) -> str:
        """Extract calendar ID from Microsoft Graph resource path"""
        # Parse resource paths like "/me/calendars/{calendar-id}/events/{event-id}"
        parts = resource.split('/')
        if 'calendars' in parts:
            calendar_index = parts.index('calendars')
            if calendar_index + 1 < len(parts):
                return parts[calendar_index + 1]
        return "primary"
    
    def _extract_event_id_from_resource(self, resource: str) -> Optional[str]:
        """Extract event ID from Microsoft Graph resource path"""
        parts = resource.split('/')
        if 'events' in parts:
            event_index = parts.index('events')
            if event_index + 1 < len(parts):
                return parts[event_index + 1]
        return None


class PollingScheduler:
    """Manages polling-based synchronization for providers without webhooks"""
    
    def __init__(self, realtime_engine: 'RealtimeSyncEngine'):
        self.engine = realtime_engine
        self.polling_schedules: Dict[str, PollingSchedule] = {}
        self.polling_task: Optional[asyncio.Task] = None
        self.is_running = False
    
    def add_polling_schedule(self, schedule: PollingSchedule):
        """Add a new polling schedule"""
        self.polling_schedules[schedule.source_id] = schedule
        schedule.calculate_next_poll()
        logger.info(f"Added polling schedule for source {schedule.source_id}")
    
    def remove_polling_schedule(self, source_id: str):
        """Remove a polling schedule"""
        if source_id in self.polling_schedules:
            del self.polling_schedules[source_id]
            logger.info(f"Removed polling schedule for source {source_id}")
    
    def update_polling_interval(self, source_id: str, new_interval_minutes: int):
        """Update polling interval for a source"""
        if source_id in self.polling_schedules:
            schedule = self.polling_schedules[source_id]
            schedule.interval_minutes = new_interval_minutes
            schedule.calculate_next_poll()
            logger.info(f"Updated polling interval for source {source_id} to {new_interval_minutes} minutes")
    
    async def start_polling(self):
        """Start the polling scheduler"""
        if self.is_running:
            return
        
        self.is_running = True
        self.polling_task = asyncio.create_task(self._polling_loop())
        logger.info("Polling scheduler started")
    
    async def stop_polling(self):
        """Stop the polling scheduler"""
        self.is_running = False
        if self.polling_task:
            self.polling_task.cancel()
            try:
                await self.polling_task
            except asyncio.CancelledError:
                pass
        logger.info("Polling scheduler stopped")
    
    async def _polling_loop(self):
        """Main polling loop"""
        while self.is_running:
            try:
                now = datetime.utcnow()
                
                # Check which sources need polling
                sources_to_poll = []
                for schedule in self.polling_schedules.values():
                    if schedule.is_active and (not schedule.next_poll or now >= schedule.next_poll):
                        sources_to_poll.append(schedule)
                
                # Poll sources concurrently
                if sources_to_poll:
                    tasks = [self._poll_source(schedule) for schedule in sources_to_poll]
                    await asyncio.gather(*tasks, return_exceptions=True)
                
                # Sleep for a short interval before checking again
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in polling loop: {e}")
                await asyncio.sleep(60)  # Back off on errors
    
    async def _poll_source(self, schedule: PollingSchedule):
        """Poll a specific source for changes"""
        try:
            logger.debug(f"Polling source {schedule.source_id}")
            
            schedule.last_poll = datetime.utcnow()
            
            # Get source configuration
            source = await self._get_source_config(schedule.source_id)
            if not source:
                logger.warning(f"Source {schedule.source_id} not found for polling")
                return
            
            # Poll each calendar in the source
            changes_detected = False
            for calendar_id in schedule.calendar_ids:
                changes = await self._check_calendar_changes(source, calendar_id)
                if changes:
                    changes_detected = True
                    
                    # Create change notifications
                    for change in changes:
                        notification = ChangeNotification(
                            id=str(uuid4()),
                            source="polling",
                            provider=schedule.provider,
                            calendar_id=calendar_id,
                            change_type=change.get('change_type', ChangeType.UPDATED),
                            event_id=change.get('event_id'),
                            timestamp=datetime.utcnow(),
                            priority=NotificationPriority.NORMAL,
                            sync_token=change.get('sync_token'),
                            metadata=change
                        )
                        
                        # Process the change
                        await self.engine.process_change_notification(notification)
            
            # Update schedule based on success/failure
            if changes_detected:
                schedule.consecutive_failures = 0
                schedule.backoff_multiplier = 1.0
            else:
                # No changes - can reduce polling frequency slightly
                schedule.backoff_multiplier = min(schedule.backoff_multiplier * 1.1, 2.0)
            
            schedule.calculate_next_poll()
            
        except Exception as e:
            logger.error(f"Error polling source {schedule.source_id}: {e}")
            
            # Increase backoff for failures
            schedule.consecutive_failures += 1
            schedule.backoff_multiplier = min(schedule.backoff_multiplier * 1.5, 4.0)
            schedule.calculate_next_poll()
    
    async def _get_source_config(self, source_id: str) -> Optional[SyncSource]:
        """Get source configuration for polling"""
        # This would typically load from storage
        # For now, return None - to be implemented with storage integration
        return None
    
    async def _check_calendar_changes(self, source: SyncSource, calendar_id: str) -> List[Dict[str, Any]]:
        """Check for changes in a specific calendar"""
        changes = []
        
        try:
            # Use sync tokens for efficient change detection
            sync_token = source.sync_tokens.get(calendar_id)
            
            if source.provider_type == CalendarProvider.GOOGLE.value:
                result = await self.engine.unified_service.google_service.get_events(
                    token_info=source.credentials,
                    calendar_id=calendar_id,
                    sync_token=sync_token
                )
                
                events = result.get('events', [])
                if events:
                    changes.extend([
                        {
                            'change_type': ChangeType.UPDATED,
                            'event_id': event.provider_id,
                            'sync_token': result.get('nextSyncToken')
                        } for event in events
                    ])
                
                # Update sync token
                if result.get('nextSyncToken'):
                    source.sync_tokens[calendar_id] = result['nextSyncToken']
            
            elif source.provider_type == CalendarProvider.MICROSOFT.value:
                delta_link = source.sync_tokens.get(calendar_id)
                result = await self.engine.unified_service.microsoft_service.get_events(
                    token_info=source.credentials,
                    calendar_id=calendar_id,
                    delta_link=delta_link
                )
                
                events = result.get('events', [])
                if events:
                    changes.extend([
                        {
                            'change_type': ChangeType.UPDATED,
                            'event_id': event.provider_id,
                            'sync_token': result.get('deltaLink')
                        } for event in events
                    ])
                
                # Update delta link
                if result.get('deltaLink'):
                    source.sync_tokens[calendar_id] = result['deltaLink']
        
        except Exception as e:
            logger.error(f"Error checking calendar changes for {calendar_id}: {e}")
        
        return changes


class RealtimeSyncEngine:
    """Main real-time synchronization engine"""
    
    def __init__(
        self,
        storage_manager: SyncStorageManager,
        sync_engine: BidirectionalSyncEngine,
        unified_service: Optional[UnifiedCalendarService] = None
    ):
        self.storage = storage_manager
        self.sync_engine = sync_engine
        self.unified_service = unified_service or UnifiedCalendarService()
        
        # Components
        self.websocket_manager = WebSocketManager()
        self.webhook_receiver = WebhookReceiver(self)
        self.polling_scheduler = PollingScheduler(self)
        
        # Change processing
        self.change_queue = asyncio.Queue()
        self.processing_task: Optional[asyncio.Task] = None
        self.is_processing = False
        
        # Rate limiting
        self.rate_limits: Dict[str, List[datetime]] = defaultdict(list)
        self.rate_limit_window = timedelta(minutes=1)
        self.rate_limit_max_requests = 60
        
        # Callbacks
        self.change_callbacks: List[Callable[[ChangeNotification], None]] = []
    
    def add_change_callback(self, callback: Callable[[ChangeNotification], None]):
        """Add a callback function to receive change notifications"""
        self.change_callbacks.append(callback)
    
    async def start(self):
        """Start the real-time sync engine"""
        logger.info("Starting real-time sync engine")
        
        # Start change processing
        if not self.is_processing:
            self.is_processing = True
            self.processing_task = asyncio.create_task(self._change_processing_loop())
        
        # Start polling scheduler
        await self.polling_scheduler.start_polling()
        
        logger.info("Real-time sync engine started")
    
    async def stop(self):
        """Stop the real-time sync engine"""
        logger.info("Stopping real-time sync engine")
        
        # Stop change processing
        self.is_processing = False
        if self.processing_task:
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass
        
        # Stop polling scheduler
        await self.polling_scheduler.stop_polling()
        
        logger.info("Real-time sync engine stopped")
    
    async def process_change_notification(self, notification: ChangeNotification):
        """Process a change notification"""
        try:
            # Check rate limits
            if not self._check_rate_limit(notification.provider.value):
                logger.warning(f"Rate limit exceeded for {notification.provider.value}, queuing change")
            
            # Add to processing queue
            await self.change_queue.put(notification)
            
            # Notify callbacks
            for callback in self.change_callbacks:
                try:
                    callback(notification)
                except Exception as e:
                    logger.warning(f"Change callback error: {e}")
            
            logger.debug(f"Queued change notification: {notification.change_type} for {notification.calendar_id}")
        
        except Exception as e:
            logger.error(f"Error processing change notification: {e}")
    
    async def _change_processing_loop(self):
        """Main loop for processing change notifications"""
        while self.is_processing:
            try:
                # Get next change notification
                try:
                    notification = await asyncio.wait_for(
                        self.change_queue.get(), 
                        timeout=5.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # Process the change
                await self._process_single_change(notification)
                
                # Mark task as done
                self.change_queue.task_done()
                
            except Exception as e:
                logger.error(f"Error in change processing loop: {e}")
                await asyncio.sleep(1)
    
    async def _process_single_change(self, notification: ChangeNotification):
        """Process a single change notification"""
        try:
            logger.debug(f"Processing change: {notification.change_type} for {notification.calendar_id}")
            
            # Get affected sync configuration
            config = await self._get_affected_sync_config(notification)
            if not config:
                logger.warning(f"No sync configuration found for change in {notification.calendar_id}")
                return
            
            # Trigger incremental sync for affected calendars
            operation_id = await self.sync_engine.sync_bidirectional(
                config,
                background_tasks=None,  # We're already in a background task
                operation_id=f"realtime_{notification.id}"
            )
            
            # Send real-time update to WebSocket clients
            await self._send_realtime_update(notification)
            
            logger.info(f"Processed change notification {notification.id}, triggered sync {operation_id}")
            
        except Exception as e:
            logger.error(f"Error processing change {notification.id}: {e}")
    
    async def _get_affected_sync_config(self, notification: ChangeNotification) -> Optional[SyncConfiguration]:
        """Get sync configuration affected by a change notification"""
        # This would load the full sync configuration and filter
        # to only include sources/destinations affected by this change
        # For now, returning None - to be implemented with proper storage integration
        return None
    
    async def _send_realtime_update(self, notification: ChangeNotification):
        """Send real-time update to WebSocket clients"""
        message = {
            "type": "calendar_change",
            "data": {
                "id": notification.id,
                "change_type": notification.change_type.value,
                "provider": notification.provider.value,
                "calendar_id": notification.calendar_id,
                "event_id": notification.event_id,
                "timestamp": notification.timestamp.isoformat(),
                "priority": notification.priority.value
            }
        }
        
        # Broadcast to subscribers
        await self.websocket_manager.broadcast_to_subscribers(
            notification.calendar_id, 
            message
        )
    
    def _check_rate_limit(self, provider: str) -> bool:
        """Check if provider is within rate limits"""
        now = datetime.utcnow()
        
        # Clean old requests
        cutoff = now - self.rate_limit_window
        self.rate_limits[provider] = [
            req_time for req_time in self.rate_limits[provider] 
            if req_time > cutoff
        ]
        
        # Check current rate
        if len(self.rate_limits[provider]) >= self.rate_limit_max_requests:
            return False
        
        # Record this request
        self.rate_limits[provider].append(now)
        return True
    
    def configure_polling_for_source(
        self, 
        source_id: str, 
        provider: CalendarProvider,
        calendar_ids: List[str],
        interval_minutes: int = 30
    ):
        """Configure polling for a source that doesn't support webhooks"""
        schedule = PollingSchedule(
            source_id=source_id,
            provider=provider,
            calendar_ids=calendar_ids,
            interval_minutes=interval_minutes
        )
        
        self.polling_scheduler.add_polling_schedule(schedule)
    
    def get_webhook_router(self) -> APIRouter:
        """Get the webhook router for FastAPI integration"""
        return self.webhook_receiver.router
    
    async def websocket_endpoint(self, websocket: WebSocket, client_id: str):
        """WebSocket endpoint for real-time updates"""
        await self.websocket_manager.connect(websocket, client_id)
        
        try:
            while True:
                # Listen for client messages (subscriptions, etc.)
                data = await websocket.receive_json()
                
                if data.get("type") == "subscribe":
                    calendar_id = data.get("calendar_id")
                    if calendar_id:
                        self.websocket_manager.subscribe(client_id, calendar_id)
                
                elif data.get("type") == "unsubscribe":
                    calendar_id = data.get("calendar_id")
                    if calendar_id:
                        self.websocket_manager.unsubscribe(client_id, calendar_id)
                
                elif data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
        
        except Exception as e:
            logger.info(f"WebSocket client {client_id} disconnected: {e}")
        finally:
            self.websocket_manager.disconnect(client_id)
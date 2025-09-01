"""
Core Bidirectional Calendar Synchronization Engine

This module implements the central synchronization engine that orchestrates
bidirectional sync across all calendar providers with event deduplication,
batch operations, and comprehensive progress tracking.
"""

import asyncio
import hashlib
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple, Any, Callable
from enum import Enum

from fastapi import BackgroundTasks
from services.calendar_event import CalendarEvent, CalendarProvider
from services.unified_calendar import UnifiedCalendarService
from sync.architecture import (
    SyncConfiguration, SyncSource, SyncDestination, 
    SyncDirection, ConflictResolution
)
from sync.storage import SyncStorageManager

logger = logging.getLogger(__name__)


class SyncOperation(str, Enum):
    """Types of sync operations"""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    METADATA_UPDATE = "metadata_update"


class SyncStatus(str, Enum):
    """Status of sync operations"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CONFLICT = "conflict"


@dataclass
class EventFingerprint:
    """Unique fingerprint for event deduplication"""
    content_hash: str
    provider_id: str
    calendar_id: str
    last_modified: datetime
    
    @classmethod
    def from_event(cls, event: CalendarEvent) -> 'EventFingerprint':
        """Create fingerprint from calendar event"""
        # Create content hash from essential fields
        content_string = f"{event.title}|{event.start_time}|{event.end_time}|{event.description}|{event.location}"
        content_hash = hashlib.sha256(content_string.encode()).hexdigest()[:16]
        
        return cls(
            content_hash=content_hash,
            provider_id=event.provider_id or "",
            calendar_id=event.calendar_id or "",
            last_modified=event.updated_at or event.created_at or datetime.utcnow()
        )


@dataclass
class SyncBatch:
    """Batch of sync operations"""
    operation: SyncOperation
    events: List[CalendarEvent]
    source_id: str
    destination_calendar_id: str
    batch_size: int = 50
    
    def split_into_chunks(self) -> List['SyncBatch']:
        """Split batch into smaller chunks for processing"""
        chunks = []
        for i in range(0, len(self.events), self.batch_size):
            chunk_events = self.events[i:i + self.batch_size]
            chunks.append(SyncBatch(
                operation=self.operation,
                events=chunk_events,
                source_id=self.source_id,
                destination_calendar_id=self.destination_calendar_id,
                batch_size=self.batch_size
            ))
        return chunks


@dataclass
class SyncProgress:
    """Progress tracking for sync operations"""
    operation_id: str
    total_batches: int
    completed_batches: int
    total_events: int
    processed_events: int
    failed_events: int
    conflicts: int
    start_time: datetime
    last_update: datetime
    status: SyncStatus
    error_messages: List[str]
    
    @property
    def progress_percentage(self) -> float:
        """Calculate progress percentage"""
        if self.total_events == 0:
            return 100.0
        return (self.processed_events / self.total_events) * 100.0
    
    @property
    def estimated_completion(self) -> Optional[datetime]:
        """Estimate completion time based on current progress"""
        if self.processed_events == 0:
            return None
            
        elapsed = (self.last_update - self.start_time).total_seconds()
        if elapsed == 0:
            return None
            
        rate = self.processed_events / elapsed
        remaining_events = self.total_events - self.processed_events
        
        if rate == 0:
            return None
            
        remaining_seconds = remaining_events / rate
        return self.last_update + timedelta(seconds=remaining_seconds)


class BidirectionalSyncEngine:
    """
    Core bidirectional synchronization engine that orchestrates sync operations
    across all calendar providers with advanced conflict resolution and deduplication
    """
    
    def __init__(
        self, 
        storage_manager: SyncStorageManager,
        unified_service: Optional[UnifiedCalendarService] = None,
        max_concurrent_operations: int = 5,
        default_batch_size: int = 50
    ):
        self.storage = storage_manager
        self.unified_service = unified_service or UnifiedCalendarService()
        self.max_concurrent_operations = max_concurrent_operations
        self.default_batch_size = default_batch_size
        
        # Track active sync operations
        self.active_operations: Dict[str, SyncProgress] = {}
        self.operation_semaphore = asyncio.Semaphore(max_concurrent_operations)
        
        # Event deduplication cache
        self.event_fingerprints: Dict[str, EventFingerprint] = {}
        
        # Callback hooks for progress updates
        self.progress_callbacks: List[Callable[[SyncProgress], None]] = []
    
    def add_progress_callback(self, callback: Callable[[SyncProgress], None]):
        """Add a callback function to receive progress updates"""
        self.progress_callbacks.append(callback)
    
    def _notify_progress(self, progress: SyncProgress):
        """Notify all registered callbacks of progress update"""
        for callback in self.progress_callbacks:
            try:
                callback(progress)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")
    
    async def sync_bidirectional(
        self, 
        config: SyncConfiguration, 
        background_tasks: BackgroundTasks,
        operation_id: Optional[str] = None
    ) -> str:
        """
        Execute comprehensive bidirectional synchronization
        
        Args:
            config: Sync configuration with sources and destination
            background_tasks: FastAPI BackgroundTasks for non-blocking execution
            operation_id: Optional operation ID for tracking
            
        Returns:
            Operation ID for tracking progress
        """
        if not operation_id:
            operation_id = f"sync_{datetime.utcnow().timestamp()}"
        
        logger.info(f"Starting bidirectional sync operation {operation_id}")
        
        # Add background task for the actual sync work
        background_tasks.add_task(
            self._execute_bidirectional_sync,
            config,
            operation_id
        )
        
        return operation_id
    
    async def _execute_bidirectional_sync(
        self,
        config: SyncConfiguration,
        operation_id: str
    ):
        """Execute the actual bidirectional sync work"""
        async with self.operation_semaphore:
            # Initialize progress tracking
            total_sources = len([s for s in config.sources if s.enabled])
            progress = SyncProgress(
                operation_id=operation_id,
                total_batches=0,  # Will be updated as we discover batches
                completed_batches=0,
                total_events=0,
                processed_events=0,
                failed_events=0,
                conflicts=0,
                start_time=datetime.utcnow(),
                last_update=datetime.utcnow(),
                status=SyncStatus.IN_PROGRESS,
                error_messages=[]
            )
            
            self.active_operations[operation_id] = progress
            self._notify_progress(progress)
            
            try:
                # Phase 1: Collect all events from sources
                logger.info(f"Phase 1: Collecting events from {total_sources} sources")
                source_events = await self._collect_source_events(config, progress)
                
                # Phase 2: Deduplicate events across sources
                logger.info("Phase 2: Deduplicating events")
                deduplicated_events = await self._deduplicate_events(source_events, progress)
                
                # Phase 3: Sync to destination
                logger.info("Phase 3: Syncing to destination")
                if config.destination:
                    await self._sync_to_destination(
                        deduplicated_events, 
                        config.destination, 
                        progress
                    )
                
                # Phase 4: Handle bidirectional updates back to sources
                logger.info("Phase 4: Processing bidirectional updates")
                await self._process_bidirectional_updates(config, progress)
                
                # Mark operation as completed
                progress.status = SyncStatus.COMPLETED
                progress.last_update = datetime.utcnow()
                self._notify_progress(progress)
                
                logger.info(f"Sync operation {operation_id} completed successfully")
                
            except Exception as e:
                logger.error(f"Sync operation {operation_id} failed: {e}")
                progress.status = SyncStatus.FAILED
                progress.error_messages.append(str(e))
                progress.last_update = datetime.utcnow()
                self._notify_progress(progress)
                raise
    
    async def _collect_source_events(
        self, 
        config: SyncConfiguration, 
        progress: SyncProgress
    ) -> Dict[str, List[CalendarEvent]]:
        """Collect events from all enabled sources"""
        source_events = {}
        
        # Calculate date range for sync (configurable)
        start_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=90)
        
        # Create tasks for concurrent collection
        collection_tasks = []
        for source in config.sources:
            if not source.enabled:
                continue
                
            collection_tasks.append(
                self._collect_source_events_single(source, start_date, end_date)
            )
        
        # Execute collections concurrently
        if collection_tasks:
            results = await asyncio.gather(*collection_tasks, return_exceptions=True)
            
            total_collected = 0
            for result in results:
                if isinstance(result, Exception):
                    error_msg = f"Error collecting from source: {result}"
                    logger.error(error_msg)
                    progress.error_messages.append(error_msg)
                    continue
                
                source_id, events = result
                source_events[source_id] = events
                total_collected += len(events)
                
                logger.info(f"Collected {len(events)} events from source {source_id}")
        
        progress.total_events = total_collected
        progress.last_update = datetime.utcnow()
        self._notify_progress(progress)
        
        return source_events
    
    async def _collect_source_events_single(
        self, 
        source: SyncSource, 
        start_date: datetime, 
        end_date: datetime
    ) -> Tuple[str, List[CalendarEvent]]:
        """Collect events from a single source"""
        events = []
        
        try:
            if source.sync_method.value == "api":
                # Direct API access
                for calendar_id in source.calendars:
                    sync_token = source.sync_tokens.get(calendar_id)
                    
                    if source.provider_type == CalendarProvider.GOOGLE.value:
                        result = await self.unified_service.google_service.get_events(
                            token_info=source.credentials,
                            calendar_id=calendar_id,
                            start_date=start_date,
                            end_date=end_date,
                            sync_token=sync_token
                        )
                        events.extend(result.get('events', []))
                        
                        # Update sync token
                        if result.get('nextSyncToken'):
                            source.sync_tokens[calendar_id] = result['nextSyncToken']
                    
                    elif source.provider_type == CalendarProvider.MICROSOFT.value:
                        delta_link = source.sync_tokens.get(calendar_id)
                        result = await self.unified_service.microsoft_service.get_events(
                            token_info=source.credentials,
                            calendar_id=calendar_id,
                            start_date=start_date,
                            end_date=end_date,
                            delta_link=delta_link
                        )
                        events.extend(result.get('events', []))
                        
                        # Update delta link
                        if result.get('deltaLink'):
                            source.sync_tokens[calendar_id] = result['deltaLink']
            
            elif source.sync_method.value == "agent":
                # Get events from agent cache
                agent_events = await self.storage.get_agent_events(source.id)
                if agent_events:
                    for event_data in agent_events:
                        try:
                            event = CalendarEvent.parse_obj(event_data)
                            events.append(event)
                        except Exception as e:
                            logger.error(f"Error parsing agent event: {e}")
            
        except Exception as e:
            logger.error(f"Error collecting events from source {source.id}: {e}")
            raise
        
        return source.id, events
    
    async def _deduplicate_events(
        self, 
        source_events: Dict[str, List[CalendarEvent]], 
        progress: SyncProgress
    ) -> Dict[str, List[CalendarEvent]]:
        """Deduplicate events across sources using content fingerprinting"""
        
        # Build fingerprint index
        fingerprint_to_events: Dict[str, List[Tuple[str, CalendarEvent]]] = defaultdict(list)
        
        for source_id, events in source_events.items():
            for event in events:
                fingerprint = EventFingerprint.from_event(event)
                fingerprint_to_events[fingerprint.content_hash].append((source_id, event))
        
        # Process duplicates
        deduplicated_events = {}
        duplicate_count = 0
        
        for content_hash, event_list in fingerprint_to_events.items():
            if len(event_list) == 1:
                # No duplicates
                source_id, event = event_list[0]
                if source_id not in deduplicated_events:
                    deduplicated_events[source_id] = []
                deduplicated_events[source_id].append(event)
            else:
                # Handle duplicates - choose the most recently updated
                duplicate_count += len(event_list) - 1
                
                # Sort by last modified time
                sorted_events = sorted(
                    event_list, 
                    key=lambda x: x[1].updated_at or x[1].created_at or datetime.min,
                    reverse=True
                )
                
                # Keep the most recent one
                source_id, best_event = sorted_events[0]
                if source_id not in deduplicated_events:
                    deduplicated_events[source_id] = []
                deduplicated_events[source_id].append(best_event)
                
                logger.debug(f"Deduplicated {len(event_list)} events with hash {content_hash}")
        
        logger.info(f"Removed {duplicate_count} duplicate events")
        
        return deduplicated_events
    
    async def _sync_to_destination(
        self, 
        source_events: Dict[str, List[CalendarEvent]], 
        destination: SyncDestination, 
        progress: SyncProgress
    ):
        """Sync all events to the destination calendar"""
        
        # Flatten all events for destination sync
        all_events = []
        for source_id, events in source_events.items():
            for event in events:
                # Add source metadata to event
                if event.description:
                    event.description += f"\n\nSynced from: {source_id}"
                else:
                    event.description = f"Synced from: {source_id}"
                all_events.append(event)
        
        if not all_events:
            logger.info("No events to sync to destination")
            return
        
        # Create batches for efficient processing
        batches = self._create_sync_batches(all_events, destination.calendar_id)
        progress.total_batches = len(batches)
        self._notify_progress(progress)
        
        # Process batches
        for i, batch in enumerate(batches):
            try:
                await self._process_sync_batch(batch, destination, progress)
                progress.completed_batches = i + 1
                progress.last_update = datetime.utcnow()
                self._notify_progress(progress)
                
            except Exception as e:
                error_msg = f"Error processing batch {i}: {e}"
                logger.error(error_msg)
                progress.error_messages.append(error_msg)
                progress.failed_events += len(batch.events)
                progress.last_update = datetime.utcnow()
                self._notify_progress(progress)
    
    def _create_sync_batches(
        self, 
        events: List[CalendarEvent], 
        destination_calendar_id: str
    ) -> List[SyncBatch]:
        """Create batches for efficient sync processing"""
        
        # Group events by operation type (for now, all are creates)
        create_events = events  # All events are creates for initial sync
        
        batches = []
        if create_events:
            batch = SyncBatch(
                operation=SyncOperation.CREATE,
                events=create_events,
                source_id="unified",
                destination_calendar_id=destination_calendar_id,
                batch_size=self.default_batch_size
            )
            batches.extend(batch.split_into_chunks())
        
        return batches
    
    async def _process_sync_batch(
        self, 
        batch: SyncBatch, 
        destination: SyncDestination, 
        progress: SyncProgress
    ):
        """Process a single sync batch"""
        
        if batch.operation == SyncOperation.CREATE:
            # Create events in destination
            created_events = await self.unified_service.create_events_in_destination(
                provider=destination.provider_type,
                calendar_id=batch.destination_calendar_id,
                credentials=destination.credentials,
                events=batch.events
            )
            
            progress.processed_events += len(created_events)
            logger.info(f"Created {len(created_events)} events in destination")
        
        # Add support for other operations (UPDATE, DELETE) as needed
    
    async def _process_bidirectional_updates(
        self, 
        config: SyncConfiguration, 
        progress: SyncProgress
    ):
        """Process any pending bidirectional updates from destination to sources"""
        
        # For now, this is a placeholder for future bidirectional update logic
        # This would handle cases where events are modified in the destination
        # and need to be propagated back to source calendars
        
        logger.info("Processing bidirectional updates (placeholder)")
        
        # Future implementation would:
        # 1. Check for changes in destination calendar since last sync
        # 2. Identify which source each event came from
        # 3. Push updates back to appropriate sources
        # 4. Handle conflicts and metadata updates
    
    def get_operation_progress(self, operation_id: str) -> Optional[SyncProgress]:
        """Get progress information for a sync operation"""
        return self.active_operations.get(operation_id)
    
    def list_active_operations(self) -> Dict[str, SyncProgress]:
        """List all active sync operations"""
        return self.active_operations.copy()
    
    async def cancel_operation(self, operation_id: str) -> bool:
        """Cancel a running sync operation"""
        if operation_id in self.active_operations:
            progress = self.active_operations[operation_id]
            progress.status = SyncStatus.FAILED
            progress.error_messages.append("Operation cancelled by user")
            progress.last_update = datetime.utcnow()
            self._notify_progress(progress)
            
            # Note: This is a simple cancellation - in a full implementation,
            # we would need to properly interrupt the running tasks
            logger.info(f"Cancelled sync operation {operation_id}")
            return True
        
        return False
    
    async def cleanup_completed_operations(self, max_age_hours: int = 24):
        """Clean up old completed operations"""
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        
        operations_to_remove = []
        for operation_id, progress in self.active_operations.items():
            if (progress.status in [SyncStatus.COMPLETED, SyncStatus.FAILED] and
                progress.last_update < cutoff_time):
                operations_to_remove.append(operation_id)
        
        for operation_id in operations_to_remove:
            del self.active_operations[operation_id]
            logger.debug(f"Cleaned up old operation {operation_id}")
        
        logger.info(f"Cleaned up {len(operations_to_remove)} old sync operations")
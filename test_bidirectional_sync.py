"""
Comprehensive Integration Tests for Bidirectional Calendar Synchronization

This test suite validates the complete Phase 5 implementation including:
- Bidirectional sync engine with event deduplication
- Conflict resolution with multiple strategies
- Real-time synchronization capabilities
- Token management with persistence
- FastAPI BackgroundTasks integration
"""

import asyncio
import pytest
import tempfile
import shutil
from datetime import datetime, timedelta
from typing import Dict, Any, List
from fastapi import FastAPI, BackgroundTasks
from fastapi.testclient import TestClient
import json
import os

# Import the components we're testing
from src.sync.sync_engine import BidirectionalSyncEngine, SyncConfiguration, SyncProgress
from src.sync.conflict_resolver import ConflictManager, ConflictStrategy
from src.sync.realtime_sync import RealtimeSyncEngine
from src.sync.token_manager import TokenManager
from src.sync.controller import CalendarSyncController
from src.sync.storage import SyncStorageManager
from src.sync.architecture import (
    SyncSource, SyncDestination, SyncAgentConfig,
    SyncDirection, SyncFrequency, SyncMethod, ConflictResolution
)
from src.services.unified_calendar import UnifiedCalendarService
from src.services.calendar_event import CalendarEvent, CalendarProvider
from src.api.sync_router import router


class MockCalendarService:
    """Mock calendar service for testing"""
    
    def __init__(self):
        self.events = {}
        self.calendars = {}
        self.call_count = 0
        
    async def get_events(self, calendar_id: str, start_date: datetime = None, end_date: datetime = None, **kwargs):
        """Mock get events"""
        self.call_count += 1
        return {
            'events': self.events.get(calendar_id, []),
            'nextSyncToken': f"sync_token_{self.call_count}",
            'deltaLink': f"delta_link_{self.call_count}"
        }
    
    async def create_event(self, calendar_id: str, event: CalendarEvent):
        """Mock create event"""
        if calendar_id not in self.events:
            self.events[calendar_id] = []
        
        event_dict = {
            'id': f"event_{len(self.events[calendar_id])}",
            'title': event.title,
            'description': event.description,
            'start_time': event.start_time.isoformat(),
            'end_time': event.end_time.isoformat(),
            'all_day': event.all_day,
            'location': event.location
        }
        self.events[calendar_id].append(event_dict)
        return event_dict
    
    async def update_event(self, calendar_id: str, event_id: str, event: CalendarEvent):
        """Mock update event"""
        if calendar_id in self.events:
            for i, existing_event in enumerate(self.events[calendar_id]):
                if existing_event['id'] == event_id:
                    self.events[calendar_id][i].update({
                        'title': event.title,
                        'description': event.description,
                        'start_time': event.start_time.isoformat(),
                        'end_time': event.end_time.isoformat(),
                        'all_day': event.all_day,
                        'location': event.location
                    })
                    return self.events[calendar_id][i]
        return None


class MockUnifiedCalendarService:
    """Mock unified calendar service for testing"""
    
    def __init__(self):
        self.google_service = MockCalendarService()
        self.microsoft_service = MockCalendarService()
        self.exchange_service = MockCalendarService()
        self.apple_service = MockCalendarService()
    
    async def get_events(self, provider: str, calendar_id: str, credentials: Dict[str, Any], **kwargs):
        """Mock get events from provider"""
        if provider == CalendarProvider.GOOGLE.value:
            return await self.google_service.get_events(calendar_id, **kwargs)
        elif provider == CalendarProvider.MICROSOFT.value:
            return await self.microsoft_service.get_events(calendar_id, **kwargs)
        return {'events': [], 'nextSyncToken': None}
    
    async def create_event(self, provider: str, calendar_id: str, credentials: Dict[str, Any], event: CalendarEvent):
        """Mock create event in provider"""
        if provider == CalendarProvider.GOOGLE.value:
            return await self.google_service.create_event(calendar_id, event)
        elif provider == CalendarProvider.MICROSOFT.value:
            return await self.microsoft_service.create_event(calendar_id, event)
        return None


class MockBackgroundTasks:
    """Mock FastAPI BackgroundTasks for testing"""
    
    def __init__(self):
        self.tasks = []
    
    def add_task(self, func, *args, **kwargs):
        """Add a background task"""
        self.tasks.append((func, args, kwargs))
    
    async def execute_all(self):
        """Execute all queued tasks"""
        for func, args, kwargs in self.tasks:
            if asyncio.iscoroutinefunction(func):
                await func(*args, **kwargs)
            else:
                func(*args, **kwargs)
        self.tasks.clear()


@pytest.fixture
async def temp_storage():
    """Create temporary storage for tests"""
    temp_dir = tempfile.mkdtemp()
    storage_path = os.path.join(temp_dir, "test_storage.db")
    
    storage = SyncStorageManager(storage_path)
    await storage.initialize()
    
    yield storage
    
    await storage.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_unified_service():
    """Create mock unified calendar service"""
    return MockUnifiedCalendarService()


@pytest.fixture
def sample_events():
    """Create sample calendar events for testing"""
    now = datetime.utcnow()
    
    return [
        CalendarEvent(
            id="event_1",
            title="Test Event 1",
            description="Description 1",
            start_time=now + timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            all_day=False,
            location="Location 1",
            calendar_id="cal_1",
            provider=CalendarProvider.GOOGLE,
            created_at=now,
            updated_at=now
        ),
        CalendarEvent(
            id="event_2",
            title="Test Event 2",
            description="Description 2",
            start_time=now + timedelta(days=1),
            end_time=now + timedelta(days=1, hours=1),
            all_day=False,
            location="Location 2",
            calendar_id="cal_2",
            provider=CalendarProvider.MICROSOFT,
            created_at=now - timedelta(hours=1),
            updated_at=now
        ),
        CalendarEvent(
            id="event_3",
            title="Conflicting Event",
            description="This will conflict",
            start_time=now + timedelta(hours=3),
            end_time=now + timedelta(hours=4),
            all_day=False,
            location="Location 3",
            calendar_id="cal_1",
            provider=CalendarProvider.GOOGLE,
            created_at=now - timedelta(minutes=30),
            updated_at=now - timedelta(minutes=15)
        )
    ]


@pytest.fixture
def sync_configuration():
    """Create sample sync configuration"""
    return SyncConfiguration(
        sources=[
            SyncSource(
                id="source_1",
                name="Google Test Source",
                provider_type=CalendarProvider.GOOGLE.value,
                calendars=["cal_1"],
                credentials={"access_token": "fake_google_token"},
                sync_method=SyncMethod.API,
                sync_direction=SyncDirection.BIDIRECTIONAL,
                enabled=True,
                sync_tokens={}
            ),
            SyncSource(
                id="source_2", 
                name="Microsoft Test Source",
                provider_type=CalendarProvider.MICROSOFT.value,
                calendars=["cal_2"],
                credentials={"access_token": "fake_microsoft_token"},
                sync_method=SyncMethod.API,
                sync_direction=SyncDirection.BIDIRECTIONAL,
                enabled=True,
                sync_tokens={}
            )
        ],
        agents=[],
        destination=SyncDestination(
            id="dest_1",
            name="Test Destination",
            provider_type=CalendarProvider.GOOGLE.value,
            calendar_id="dest_cal",
            credentials={"access_token": "fake_dest_token"},
            conflict_resolution=ConflictResolution.LATEST_WINS,
            color_management="category_based",
            categories={}
        ),
        sync_frequency=SyncFrequency.EVERY_15_MINUTES,
        global_settings={}
    )


class TestBidirectionalSyncEngine:
    """Test the bidirectional sync engine"""
    
    @pytest.mark.asyncio
    async def test_sync_engine_initialization(self, temp_storage, mock_unified_service):
        """Test sync engine initialization"""
        engine = BidirectionalSyncEngine(temp_storage, mock_unified_service)
        assert engine is not None
        assert engine.storage == temp_storage
        assert engine.unified_service == mock_unified_service
        assert engine.active_operations == {}
    
    @pytest.mark.asyncio
    async def test_bidirectional_sync_execution(self, temp_storage, mock_unified_service, sync_configuration, sample_events):
        """Test bidirectional sync execution"""
        engine = BidirectionalSyncEngine(temp_storage, mock_unified_service)
        background_tasks = MockBackgroundTasks()
        
        # Add some events to the mock services
        mock_unified_service.google_service.events["cal_1"] = [
            {
                'id': 'event_1',
                'title': sample_events[0].title,
                'start_time': sample_events[0].start_time.isoformat(),
                'end_time': sample_events[0].end_time.isoformat(),
                'all_day': False
            }
        ]
        
        # Execute sync
        operation_id = await engine.sync_bidirectional(sync_configuration, background_tasks)
        
        assert operation_id is not None
        assert operation_id in engine.active_operations
        assert len(background_tasks.tasks) > 0
        
        # Execute background tasks
        await background_tasks.execute_all()
        
        # Verify operation completed
        progress = engine.active_operations.get(operation_id)
        assert progress is not None
        assert progress.status in ["completed", "in_progress"]  # Might still be running


class TestConflictResolution:
    """Test conflict resolution system"""
    
    @pytest.mark.asyncio
    async def test_conflict_manager_initialization(self, temp_storage):
        """Test conflict manager initialization"""
        manager = ConflictManager(temp_storage)
        assert manager is not None
        assert manager.storage == temp_storage
    
    @pytest.mark.asyncio
    async def test_conflict_detection(self, temp_storage, sample_events):
        """Test conflict detection"""
        manager = ConflictManager(temp_storage)
        
        # Create two conflicting events
        event1 = sample_events[0]
        event2 = CalendarEvent(
            id="event_1",  # Same ID as event1
            title="Updated Event 1",
            description="Updated description",
            start_time=event1.start_time,
            end_time=event1.end_time + timedelta(minutes=30),
            all_day=False,
            location="Updated Location",
            calendar_id=event1.calendar_id,
            provider=event1.provider,
            created_at=event1.created_at,
            updated_at=event1.updated_at + timedelta(minutes=5)
        )
        
        conflicts = await manager.detector.detect_conflicts([event1], [event2])
        assert len(conflicts) > 0
        
        conflict = conflicts[0]
        assert conflict.source_event.id == event1.id
        assert conflict.destination_event.id == event2.id
        assert len(conflict.conflicting_fields) > 0
    
    @pytest.mark.asyncio
    async def test_conflict_resolution_strategies(self, temp_storage, sample_events):
        """Test different conflict resolution strategies"""
        manager = ConflictManager(temp_storage)
        
        event1 = sample_events[0]
        event2 = CalendarEvent(
            id="event_1",
            title="Updated Event 1",
            description="Updated description",
            start_time=event1.start_time,
            end_time=event1.end_time + timedelta(minutes=30),
            all_day=False,
            location="Updated Location",
            calendar_id=event1.calendar_id,
            provider=event1.provider,
            created_at=event1.created_at,
            updated_at=event1.updated_at + timedelta(minutes=5)
        )
        
        conflicts = await manager.detector.detect_conflicts([event1], [event2])
        conflict = conflicts[0]
        
        # Test SOURCE_WINS strategy
        resolved = await manager.resolver.resolve_conflict(conflict, ConflictStrategy.SOURCE_WINS)
        assert resolved.title == event1.title
        
        # Test DESTINATION_WINS strategy
        resolved = await manager.resolver.resolve_conflict(conflict, ConflictStrategy.DESTINATION_WINS)
        assert resolved.title == event2.title
        
        # Test LATEST_WINS strategy
        resolved = await manager.resolver.resolve_conflict(conflict, ConflictStrategy.LATEST_WINS)
        assert resolved.title == event2.title  # event2 has later updated_at


class TestTokenManager:
    """Test sync token management"""
    
    @pytest.mark.asyncio
    async def test_token_manager_initialization(self, temp_storage, mock_unified_service):
        """Test token manager initialization"""
        manager = TokenManager(temp_storage, mock_unified_service)
        await manager.initialize()
        
        assert manager is not None
        assert manager.storage == temp_storage
        assert manager.unified_service == mock_unified_service
    
    @pytest.mark.asyncio
    async def test_token_storage_and_retrieval(self, temp_storage, mock_unified_service):
        """Test token storage and retrieval"""
        manager = TokenManager(temp_storage, mock_unified_service)
        await manager.initialize()
        
        # Store a token
        await manager.store_sync_token("source_1", "cal_1", "test_token", datetime.utcnow())
        
        # Retrieve the token
        token = await manager.get_sync_token("source_1", "cal_1")
        
        assert token is not None
        assert token.value == "test_token"
        assert token.source_id == "source_1"
        assert token.calendar_id == "cal_1"
    
    @pytest.mark.asyncio
    async def test_token_validation_and_refresh(self, temp_storage, mock_unified_service):
        """Test token validation and refresh"""
        manager = TokenManager(temp_storage, mock_unified_service)
        await manager.initialize()
        
        # Store an expired token
        expired_time = datetime.utcnow() - timedelta(hours=2)
        await manager.store_sync_token("source_1", "cal_1", "expired_token", expired_time)
        
        # Validate (should fail for old token)
        is_valid = await manager.validator.validate_token("source_1", "cal_1", "expired_token")
        assert not is_valid
        
        # Test refresh (mock behavior)
        refreshed = await manager.refresh_token("source_1", "cal_1")
        assert refreshed is not None


class TestRealtimeSync:
    """Test real-time synchronization"""
    
    @pytest.mark.asyncio
    async def test_realtime_sync_engine_initialization(self, temp_storage, mock_unified_service):
        """Test real-time sync engine initialization"""
        sync_engine = BidirectionalSyncEngine(temp_storage, mock_unified_service)
        realtime_engine = RealtimeSyncEngine(temp_storage, sync_engine, mock_unified_service)
        
        assert realtime_engine is not None
        assert realtime_engine.storage == temp_storage
        assert realtime_engine.sync_engine == sync_engine
        assert realtime_engine.unified_service == mock_unified_service
    
    @pytest.mark.asyncio
    async def test_webhook_receiver(self, temp_storage, mock_unified_service):
        """Test webhook receiver functionality"""
        sync_engine = BidirectionalSyncEngine(temp_storage, mock_unified_service)
        realtime_engine = RealtimeSyncEngine(temp_storage, sync_engine, mock_unified_service)
        
        await realtime_engine.start()
        
        # Simulate webhook payload
        webhook_data = {
            'provider': 'google',
            'calendar_id': 'cal_1',
            'changes': [
                {
                    'type': 'created',
                    'event_id': 'new_event_1'
                }
            ]
        }
        
        # Process webhook
        result = await realtime_engine.webhook_receiver.process_webhook('google', webhook_data)
        
        assert result is not None
        assert 'status' in result


class TestSyncController:
    """Test the sync controller integration"""
    
    @pytest.mark.asyncio
    async def test_controller_initialization(self, temp_storage):
        """Test controller initialization"""
        controller = CalendarSyncController(temp_storage)
        await controller.initialize()
        
        assert controller is not None
        assert controller.storage == temp_storage
        assert controller._initialized is True
        
        await controller.shutdown()
        assert controller._initialized is False
    
    @pytest.mark.asyncio
    async def test_sync_all_calendars_with_background_tasks(self, temp_storage, sync_configuration):
        """Test sync all calendars with background tasks"""
        controller = CalendarSyncController(temp_storage)
        background_tasks = MockBackgroundTasks()
        
        # Save configuration
        await controller.save_configuration(sync_configuration)
        
        # Execute sync
        result = await controller.sync_all_calendars(background_tasks)
        
        assert result is not None
        assert result['status'] == 'started'
        assert 'operation_id' in result
        assert len(background_tasks.tasks) > 0
    
    @pytest.mark.asyncio
    async def test_sync_single_source_with_background_tasks(self, temp_storage, sync_configuration):
        """Test sync single source with background tasks"""
        controller = CalendarSyncController(temp_storage)
        background_tasks = MockBackgroundTasks()
        
        # Save configuration
        await controller.save_configuration(sync_configuration)
        
        # Execute single source sync
        result = await controller.sync_single_source('source_1', background_tasks)
        
        assert result is not None
        assert result['status'] == 'started'
        assert result['source_id'] == 'source_1'
        assert 'operation_id' in result
        assert len(background_tasks.tasks) > 0


class TestAPIIntegration:
    """Test API router integration with FastAPI"""
    
    def setup_method(self):
        """Setup test client"""
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)
    
    def test_sync_endpoints_accept_background_tasks(self):
        """Test that sync endpoints properly accept background tasks"""
        # Test sync all endpoint
        response = self.client.post("/sync/run")
        # Should not fail due to missing background tasks parameter
        assert response.status_code != 422  # Unprocessable Entity
        
        # Test sync single source endpoint
        response = self.client.post("/sync/run/test_source")
        assert response.status_code != 422
        
        # Test import endpoint
        response = self.client.post("/sync/import/test_source", json=[])
        assert response.status_code != 422


class TestEndToEndScenarios:
    """Test complete end-to-end scenarios"""
    
    @pytest.mark.asyncio
    async def test_complete_bidirectional_sync_flow(self, temp_storage, mock_unified_service, sync_configuration, sample_events):
        """Test complete bidirectional sync flow"""
        # Initialize components
        controller = CalendarSyncController(temp_storage)
        await controller.initialize()
        
        # Save configuration
        await controller.save_configuration(sync_configuration)
        
        # Add mock events to services
        mock_unified_service.google_service.events["cal_1"] = [
            {
                'id': 'event_1',
                'title': sample_events[0].title,
                'start_time': sample_events[0].start_time.isoformat(),
                'end_time': sample_events[0].end_time.isoformat(),
                'all_day': False
            }
        ]
        
        mock_unified_service.microsoft_service.events["cal_2"] = [
            {
                'id': 'event_2',
                'title': sample_events[1].title,
                'start_time': sample_events[1].start_time.isoformat(),
                'end_time': sample_events[1].end_time.isoformat(),
                'all_day': False
            }
        ]
        
        # Execute sync with background tasks
        background_tasks = MockBackgroundTasks()
        result = await controller.sync_all_calendars(background_tasks)
        
        assert result['status'] == 'started'
        assert 'operation_id' in result
        
        # Execute background tasks
        await background_tasks.execute_all()
        
        # Verify sync completed (check operation status)
        operation_id = result['operation_id']
        progress = controller.sync_engine.active_operations.get(operation_id)
        assert progress is not None
        
        await controller.shutdown()
    
    @pytest.mark.asyncio
    async def test_conflict_resolution_end_to_end(self, temp_storage, mock_unified_service, sync_configuration):
        """Test end-to-end conflict resolution"""
        controller = CalendarSyncController(temp_storage)
        await controller.initialize()
        
        # Set conflict resolution to LATEST_WINS
        sync_configuration.destination.conflict_resolution = ConflictResolution.LATEST_WINS
        await controller.save_configuration(sync_configuration)
        
        # Create conflicting events in source and destination
        now = datetime.utcnow()
        
        # Source event (older)
        mock_unified_service.google_service.events["cal_1"] = [
            {
                'id': 'conflict_event',
                'title': 'Source Event',
                'start_time': (now + timedelta(hours=1)).isoformat(),
                'end_time': (now + timedelta(hours=2)).isoformat(),
                'all_day': False,
                'updated_at': (now - timedelta(minutes=30)).isoformat()
            }
        ]
        
        # Destination event (newer)
        mock_unified_service.google_service.events["dest_cal"] = [
            {
                'id': 'conflict_event',
                'title': 'Destination Event',
                'start_time': (now + timedelta(hours=1)).isoformat(),
                'end_time': (now + timedelta(hours=2)).isoformat(),
                'all_day': False,
                'updated_at': now.isoformat()
            }
        ]
        
        # Execute sync
        background_tasks = MockBackgroundTasks()
        result = await controller.sync_all_calendars(background_tasks)
        
        assert result['status'] == 'started'
        
        # Execute background tasks to complete sync
        await background_tasks.execute_all()
        
        await controller.shutdown()
    
    @pytest.mark.asyncio
    async def test_real_time_sync_with_webhooks(self, temp_storage, mock_unified_service, sync_configuration):
        """Test real-time sync with webhook processing"""
        controller = CalendarSyncController(temp_storage)
        await controller.initialize()
        
        await controller.save_configuration(sync_configuration)
        
        # Start real-time sync engine
        realtime_engine = controller.realtime_engine
        await realtime_engine.start()
        
        # Simulate webhook notification
        webhook_data = {
            'provider': 'google',
            'calendar_id': 'cal_1',
            'changes': [
                {
                    'type': 'created',
                    'event_id': 'new_webhook_event'
                }
            ]
        }
        
        # Process webhook
        result = await realtime_engine.webhook_receiver.process_webhook('google', webhook_data)
        
        assert result is not None
        assert 'status' in result
        
        await realtime_engine.stop()
        await controller.shutdown()


def run_tests():
    """Run all tests"""
    import subprocess
    import sys
    
    # Run pytest on this file
    result = subprocess.run([
        sys.executable, "-m", "pytest", __file__, "-v", "--asyncio-mode=auto"
    ], capture_output=True, text=True)
    
    print("Test Results:")
    print("=" * 50)
    print(result.stdout)
    if result.stderr:
        print("Errors:")
        print(result.stderr)
    
    return result.returncode == 0


if __name__ == "__main__":
    # Run tests when executed directly
    success = run_tests()
    exit(0 if success else 1)
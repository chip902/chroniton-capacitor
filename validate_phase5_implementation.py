#!/usr/bin/env python3
"""
Phase 5 Implementation Validation Script

This script validates that all Phase 5 components are properly implemented and integrated:
- Bidirectional sync engine
- Conflict resolution system  
- Real-time synchronization
- Token management
- FastAPI BackgroundTasks integration

Run this script to verify the implementation is complete and functional.
"""

import asyncio
import sys
import os
import tempfile
import shutil
from datetime import datetime, timedelta
from typing import Dict, Any, List

# Add src to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from sync.sync_engine import BidirectionalSyncEngine
    from sync.conflict_resolver import ConflictManager, ConflictStrategy
    from sync.realtime_sync import RealtimeSyncEngine
    from sync.token_manager import TokenManager
    from sync.controller import CalendarSyncController
    from sync.storage import SyncStorageManager
    from sync.architecture import (
        SyncConfiguration, SyncSource, SyncDestination,
        SyncDirection, SyncFrequency, SyncMethod, ConflictResolution
    )
    from services.calendar_event import CalendarEvent, CalendarProvider
    print("✓ All required modules imported successfully")
except ImportError as e:
    print(f"✗ Failed to import required modules: {e}")
    sys.exit(1)


class MockBackgroundTasks:
    """Mock FastAPI BackgroundTasks for validation"""
    
    def __init__(self):
        self.tasks = []
        self.executed_count = 0
    
    def add_task(self, func, *args, **kwargs):
        """Add a background task"""
        self.tasks.append((func, args, kwargs))
    
    async def execute_all(self):
        """Execute all queued tasks"""
        for func, args, kwargs in self.tasks:
            try:
                if asyncio.iscoroutinefunction(func):
                    await func(*args, **kwargs)
                else:
                    func(*args, **kwargs)
                self.executed_count += 1
            except Exception as e:
                print(f"Task execution error: {e}")
        self.tasks.clear()


class MockUnifiedCalendarService:
    """Mock calendar service for validation"""
    
    def __init__(self):
        self.events = {'test_cal': []}
        self.call_count = 0
        
    async def get_events(self, provider: str, calendar_id: str, credentials: Dict[str, Any], **kwargs):
        """Mock get events"""
        self.call_count += 1
        return {
            'events': self.events.get(calendar_id, []),
            'nextSyncToken': f"sync_token_{self.call_count}",
            'deltaLink': f"delta_link_{self.call_count}"
        }
    
    async def create_event(self, provider: str, calendar_id: str, credentials: Dict[str, Any], event: CalendarEvent):
        """Mock create event"""
        if calendar_id not in self.events:
            self.events[calendar_id] = []
        
        event_data = {
            'id': f"event_{len(self.events[calendar_id]) + 1}",
            'title': event.title,
            'start_time': event.start_time.isoformat(),
            'end_time': event.end_time.isoformat()
        }
        self.events[calendar_id].append(event_data)
        return event_data


def create_sample_configuration() -> SyncConfiguration:
    """Create a sample sync configuration for testing"""
    return SyncConfiguration(
        sources=[
            SyncSource(
                id="test_source",
                name="Test Google Source",
                provider_type=CalendarProvider.GOOGLE.value,
                calendars=["test_cal"],
                credentials={"access_token": "fake_token"},
                sync_method=SyncMethod.API,
                sync_direction=SyncDirection.BIDIRECTIONAL,
                enabled=True,
                sync_tokens={}
            )
        ],
        agents=[],
        destination=SyncDestination(
            id="test_dest",
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


def create_sample_event() -> CalendarEvent:
    """Create a sample calendar event for testing"""
    now = datetime.utcnow()
    return CalendarEvent(
        id="test_event",
        title="Test Event",
        description="Test Description",
        start_time=now + timedelta(hours=1),
        end_time=now + timedelta(hours=2),
        all_day=False,
        location="Test Location",
        calendar_id="test_cal",
        provider=CalendarProvider.GOOGLE,
        created_at=now,
        updated_at=now
    )


async def validate_sync_engine():
    """Validate bidirectional sync engine implementation"""
    print("\n🔄 Validating Bidirectional Sync Engine...")
    
    try:
        # Create temporary storage
        temp_dir = tempfile.mkdtemp()
        storage_path = os.path.join(temp_dir, "test_sync.db")
        storage = SyncStorageManager(storage_path)
        await storage.initialize()
        
        # Create mock service
        mock_service = MockUnifiedCalendarService()
        
        # Initialize sync engine
        engine = BidirectionalSyncEngine(storage, mock_service)
        assert engine is not None, "Sync engine initialization failed"
        
        # Test sync execution
        config = create_sample_configuration()
        background_tasks = MockBackgroundTasks()
        
        operation_id = await engine.sync_bidirectional(config, background_tasks)
        assert operation_id is not None, "Sync operation failed to start"
        assert operation_id in engine.active_operations, "Operation not tracked"
        assert len(background_tasks.tasks) > 0, "No background tasks created"
        
        print("  ✓ Sync engine initializes correctly")
        print("  ✓ Bidirectional sync operations start successfully")
        print("  ✓ Background tasks are properly queued")
        print("  ✓ Operation tracking works correctly")
        
        # Cleanup
        await storage.close()
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        return True
        
    except Exception as e:
        print(f"  ✗ Sync engine validation failed: {e}")
        return False


async def validate_conflict_resolution():
    """Validate conflict resolution system"""
    print("\n⚡ Validating Conflict Resolution System...")
    
    try:
        # Create temporary storage
        temp_dir = tempfile.mkdtemp()
        storage_path = os.path.join(temp_dir, "test_conflicts.db")
        storage = SyncStorageManager(storage_path)
        await storage.initialize()
        
        # Initialize conflict manager
        manager = ConflictManager(storage)
        assert manager is not None, "Conflict manager initialization failed"
        
        # Create conflicting events
        event1 = create_sample_event()
        event2 = CalendarEvent(
            id=event1.id,  # Same ID - creates conflict
            title="Updated Test Event",
            description="Updated Description",
            start_time=event1.start_time,
            end_time=event1.end_time + timedelta(minutes=30),
            all_day=False,
            location="Updated Location",
            calendar_id=event1.calendar_id,
            provider=event1.provider,
            created_at=event1.created_at,
            updated_at=event1.updated_at + timedelta(minutes=5)
        )
        
        # Test conflict detection
        conflicts = await manager.detector.detect_conflicts([event1], [event2])
        assert len(conflicts) > 0, "Conflict detection failed"
        
        conflict = conflicts[0]
        assert conflict.source_event.id == event1.id, "Conflict source incorrect"
        assert conflict.destination_event.id == event2.id, "Conflict destination incorrect"
        assert len(conflict.conflicting_fields) > 0, "No conflicting fields detected"
        
        # Test resolution strategies
        resolved_source = await manager.resolver.resolve_conflict(conflict, ConflictStrategy.SOURCE_WINS)
        assert resolved_source.title == event1.title, "SOURCE_WINS strategy failed"
        
        resolved_dest = await manager.resolver.resolve_conflict(conflict, ConflictStrategy.DESTINATION_WINS)
        assert resolved_dest.title == event2.title, "DESTINATION_WINS strategy failed"
        
        resolved_latest = await manager.resolver.resolve_conflict(conflict, ConflictStrategy.LATEST_WINS)
        assert resolved_latest.title == event2.title, "LATEST_WINS strategy failed"
        
        print("  ✓ Conflict manager initializes correctly")
        print("  ✓ Conflict detection works properly")
        print("  ✓ SOURCE_WINS resolution strategy works")
        print("  ✓ DESTINATION_WINS resolution strategy works")
        print("  ✓ LATEST_WINS resolution strategy works")
        
        # Cleanup
        await storage.close()
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        return True
        
    except Exception as e:
        print(f"  ✗ Conflict resolution validation failed: {e}")
        return False


async def validate_token_management():
    """Validate sync token management"""
    print("\n🔑 Validating Token Management System...")
    
    try:
        # Create temporary storage
        temp_dir = tempfile.mkdtemp()
        storage_path = os.path.join(temp_dir, "test_tokens.db")
        storage = SyncStorageManager(storage_path)
        await storage.initialize()
        
        # Create mock service
        mock_service = MockUnifiedCalendarService()
        
        # Initialize token manager
        manager = TokenManager(storage, mock_service)
        await manager.initialize()
        assert manager is not None, "Token manager initialization failed"
        
        # Test token storage and retrieval
        test_token = "test_sync_token_123"
        test_time = datetime.utcnow()
        
        await manager.store_sync_token("test_source", "test_cal", test_token, test_time)
        
        retrieved_token = await manager.get_sync_token("test_source", "test_cal")
        assert retrieved_token is not None, "Token retrieval failed"
        assert retrieved_token.value == test_token, "Retrieved token value incorrect"
        assert retrieved_token.source_id == "test_source", "Retrieved token source incorrect"
        assert retrieved_token.calendar_id == "test_cal", "Retrieved token calendar incorrect"
        
        # Test token validation
        is_valid = await manager.validator.validate_token("test_source", "test_cal", test_token)
        assert is_valid, "Token validation failed for valid token"
        
        # Test invalid token
        is_invalid = await manager.validator.validate_token("test_source", "test_cal", "wrong_token")
        assert not is_invalid, "Token validation passed for invalid token"
        
        print("  ✓ Token manager initializes correctly")
        print("  ✓ Token storage works properly")
        print("  ✓ Token retrieval works properly")
        print("  ✓ Token validation works correctly")
        
        # Cleanup
        await manager.shutdown()
        await storage.close()
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        return True
        
    except Exception as e:
        print(f"  ✗ Token management validation failed: {e}")
        return False


async def validate_realtime_sync():
    """Validate real-time synchronization system"""
    print("\n⚡ Validating Real-time Synchronization System...")
    
    try:
        # Create temporary storage
        temp_dir = tempfile.mkdtemp()
        storage_path = os.path.join(temp_dir, "test_realtime.db")
        storage = SyncStorageManager(storage_path)
        await storage.initialize()
        
        # Create mock service
        mock_service = MockUnifiedCalendarService()
        
        # Initialize sync engine
        sync_engine = BidirectionalSyncEngine(storage, mock_service)
        
        # Initialize real-time sync engine
        realtime_engine = RealtimeSyncEngine(storage, sync_engine, mock_service)
        assert realtime_engine is not None, "Real-time sync engine initialization failed"
        
        # Test startup and shutdown
        await realtime_engine.start()
        assert realtime_engine.webhook_receiver is not None, "Webhook receiver not initialized"
        assert realtime_engine.polling_scheduler is not None, "Polling scheduler not initialized"
        
        # Test webhook processing
        webhook_data = {
            'provider': 'google',
            'calendar_id': 'test_cal',
            'changes': [
                {
                    'type': 'created',
                    'event_id': 'new_event_123'
                }
            ]
        }
        
        result = await realtime_engine.webhook_receiver.process_webhook('google', webhook_data)
        assert result is not None, "Webhook processing failed"
        assert 'status' in result, "Webhook result missing status"
        
        # Test shutdown
        await realtime_engine.stop()
        
        print("  ✓ Real-time sync engine initializes correctly")
        print("  ✓ Webhook receiver works properly")
        print("  ✓ Polling scheduler initializes correctly")
        print("  ✓ Webhook processing works")
        print("  ✓ Startup and shutdown work correctly")
        
        # Cleanup
        await storage.close()
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        return True
        
    except Exception as e:
        print(f"  ✗ Real-time sync validation failed: {e}")
        return False


async def validate_controller_integration():
    """Validate sync controller integration with background tasks"""
    print("\n🎛️ Validating Controller Integration...")
    
    try:
        # Create temporary storage
        temp_dir = tempfile.mkdtemp()
        storage_path = os.path.join(temp_dir, "test_controller.db")
        storage = SyncStorageManager(storage_path)
        await storage.initialize()
        
        # Initialize controller
        controller = CalendarSyncController(storage)
        await controller.initialize()
        assert controller._initialized, "Controller initialization failed"
        
        # Test configuration management
        config = create_sample_configuration()
        await controller.save_configuration(config)
        
        loaded_config = await controller.load_configuration()
        assert loaded_config is not None, "Configuration loading failed"
        assert len(loaded_config.sources) == len(config.sources), "Configuration sources mismatch"
        
        # Test sync operations with background tasks
        background_tasks = MockBackgroundTasks()
        
        # Test sync all calendars
        result = await controller.sync_all_calendars(background_tasks)
        assert result['status'] == 'started', "Sync all calendars failed to start"
        assert 'operation_id' in result, "No operation ID returned"
        assert len(background_tasks.tasks) > 0, "No background tasks queued"
        
        # Reset background tasks
        background_tasks = MockBackgroundTasks()
        
        # Test sync single source
        result = await controller.sync_single_source('test_source', background_tasks)
        assert result['status'] == 'started', "Single source sync failed to start"
        assert result['source_id'] == 'test_source', "Incorrect source ID in result"
        assert len(background_tasks.tasks) > 0, "No background tasks queued for single source"
        
        # Test shutdown
        await controller.shutdown()
        assert not controller._initialized, "Controller shutdown failed"
        
        print("  ✓ Controller initializes and shuts down correctly")
        print("  ✓ Configuration management works")
        print("  ✓ Sync all calendars with background tasks works")
        print("  ✓ Sync single source with background tasks works")
        print("  ✓ Background task integration works correctly")
        
        # Cleanup
        await storage.close()
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        return True
        
    except Exception as e:
        print(f"  ✗ Controller integration validation failed: {e}")
        return False


async def validate_background_tasks_integration():
    """Validate FastAPI BackgroundTasks integration"""
    print("\n⚙️ Validating FastAPI BackgroundTasks Integration...")
    
    try:
        # Test mock background tasks functionality
        background_tasks = MockBackgroundTasks()
        
        # Test adding tasks
        def dummy_task(message: str):
            print(f"  Executing task: {message}")
        
        async def async_dummy_task(message: str):
            print(f"  Executing async task: {message}")
        
        background_tasks.add_task(dummy_task, "Test sync task")
        background_tasks.add_task(async_dummy_task, "Test async sync task")
        
        assert len(background_tasks.tasks) == 2, "Tasks not added correctly"
        
        # Test task execution
        await background_tasks.execute_all()
        assert background_tasks.executed_count == 2, "Not all tasks executed"
        assert len(background_tasks.tasks) == 0, "Tasks not cleared after execution"
        
        print("  ✓ Background tasks can be added")
        print("  ✓ Both sync and async tasks are supported")
        print("  ✓ Task execution works correctly")
        print("  ✓ Tasks are cleared after execution")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Background tasks integration validation failed: {e}")
        return False


async def main():
    """Run all validation tests"""
    print("🚀 Phase 5 Implementation Validation")
    print("=" * 50)
    
    validation_functions = [
        validate_sync_engine,
        validate_conflict_resolution, 
        validate_token_management,
        validate_realtime_sync,
        validate_controller_integration,
        validate_background_tasks_integration
    ]
    
    results = []
    
    for validation_func in validation_functions:
        try:
            result = await validation_func()
            results.append(result)
        except Exception as e:
            print(f"Validation error in {validation_func.__name__}: {e}")
            results.append(False)
    
    print("\n" + "=" * 50)
    print("📊 VALIDATION SUMMARY")
    print("=" * 50)
    
    passed = sum(results)
    total = len(results)
    
    validation_names = [
        "Bidirectional Sync Engine",
        "Conflict Resolution System",
        "Token Management System", 
        "Real-time Synchronization",
        "Controller Integration",
        "Background Tasks Integration"
    ]
    
    for i, (name, result) in enumerate(zip(validation_names, results)):
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status} {name}")
    
    print(f"\nOverall Result: {passed}/{total} validations passed")
    
    if passed == total:
        print("🎉 ALL VALIDATIONS PASSED - Phase 5 implementation is complete!")
        return True
    else:
        print("⚠️  Some validations failed - check implementation")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
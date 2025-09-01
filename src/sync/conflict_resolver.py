"""
Advanced Conflict Resolution System

This module implements sophisticated conflict detection and resolution strategies
for bidirectional calendar synchronization, with field-level conflict handling,
audit trails, and manual resolution queues.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple, Set
import json
from uuid import uuid4

from services.calendar_event import CalendarEvent
from sync.architecture import ConflictResolution
from sync.storage import SyncStorageManager

logger = logging.getLogger(__name__)


class ConflictType(str, Enum):
    """Types of conflicts that can occur during sync"""
    TIME_OVERLAP = "time_overlap"           # Event time conflicts
    DUPLICATE_CONTENT = "duplicate_content" # Same event from multiple sources
    METADATA_MISMATCH = "metadata_mismatch" # Different metadata for same event
    PROVIDER_CONFLICT = "provider_conflict" # Provider-specific conflicts
    FIELD_LEVEL = "field_level"            # Specific field conflicts


class ConflictSeverity(str, Enum):
    """Severity levels for conflicts"""
    LOW = "low"         # Minor differences that can be auto-resolved
    MEDIUM = "medium"   # Significant differences requiring attention
    HIGH = "high"       # Critical conflicts requiring manual intervention
    CRITICAL = "critical" # Data integrity issues


class FieldConflictType(str, Enum):
    """Types of field-level conflicts"""
    VALUE_MISMATCH = "value_mismatch"       # Different values for same field
    PRESENCE_MISMATCH = "presence_mismatch" # Field present in one but not other
    TYPE_MISMATCH = "type_mismatch"         # Different data types
    FORMAT_MISMATCH = "format_mismatch"     # Different formats (e.g., time zones)


@dataclass
class FieldConflict:
    """Represents a conflict in a specific event field"""
    field_name: str
    conflict_type: FieldConflictType
    source_value: Any
    destination_value: Any
    source_provider: str
    destination_provider: str
    confidence_score: float = 0.0  # 0.0 = low confidence, 1.0 = high confidence
    resolution_suggestion: Optional[str] = None


@dataclass
class ConflictContext:
    """Additional context for conflict resolution"""
    source_event_history: List[Dict[str, Any]] = field(default_factory=list)
    destination_event_history: List[Dict[str, Any]] = field(default_factory=list)
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    similar_conflict_resolutions: List[str] = field(default_factory=list)
    provider_capabilities: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class ConflictResolutionResult:
    """Result of conflict resolution"""
    resolved_event: CalendarEvent
    resolution_strategy_used: ConflictResolution
    field_resolutions: Dict[str, str]
    confidence_score: float
    requires_manual_review: bool = False
    resolution_notes: List[str] = field(default_factory=list)


@dataclass
class SyncConflict:
    """Represents a synchronization conflict between events"""
    id: str
    conflict_type: ConflictType
    severity: ConflictSeverity
    source_event: CalendarEvent
    destination_event: CalendarEvent
    field_conflicts: List[FieldConflict]
    context: ConflictContext
    created_at: datetime
    updated_at: datetime
    resolution_deadline: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    
    # Resolution state
    is_resolved: bool = False
    resolution_result: Optional[ConflictResolutionResult] = None
    resolved_by: Optional[str] = None  # User ID or "system"
    resolved_at: Optional[datetime] = None


class ConflictDetector:
    """Detects conflicts between calendar events"""
    
    def __init__(self):
        self.detection_rules = {
            'title': self._detect_title_conflicts,
            'time': self._detect_time_conflicts,
            'location': self._detect_location_conflicts,
            'description': self._detect_description_conflicts,
            'attendees': self._detect_attendee_conflicts,
            'recurrence': self._detect_recurrence_conflicts
        }
    
    async def detect_conflicts(
        self,
        source_event: CalendarEvent,
        destination_event: CalendarEvent,
        detection_threshold: float = 0.8
    ) -> Optional[SyncConflict]:
        """
        Detect conflicts between source and destination events
        
        Args:
            source_event: Event from source calendar
            destination_event: Event from destination calendar
            detection_threshold: Minimum similarity to consider events as conflicts
            
        Returns:
            SyncConflict if conflicts detected, None otherwise
        """
        
        # Quick similarity check
        similarity = self._calculate_event_similarity(source_event, destination_event)
        if similarity < detection_threshold:
            return None
        
        # Detailed field-level conflict detection
        field_conflicts = []
        
        for field_name, detector_func in self.detection_rules.items():
            conflicts = await detector_func(source_event, destination_event)
            field_conflicts.extend(conflicts)
        
        if not field_conflicts:
            return None
        
        # Determine conflict type and severity
        conflict_type, severity = self._categorize_conflict(field_conflicts)
        
        # Create conflict object
        conflict = SyncConflict(
            id=str(uuid4()),
            conflict_type=conflict_type,
            severity=severity,
            source_event=source_event,
            destination_event=destination_event,
            field_conflicts=field_conflicts,
            context=ConflictContext(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            resolution_deadline=self._calculate_resolution_deadline(severity)
        )
        
        return conflict
    
    def _calculate_event_similarity(
        self, 
        event1: CalendarEvent, 
        event2: CalendarEvent
    ) -> float:
        """Calculate similarity score between two events"""
        similarity_factors = []
        
        # Title similarity (weighted heavily)
        title_sim = self._text_similarity(event1.title or "", event2.title or "")
        similarity_factors.append(title_sim * 0.4)
        
        # Time similarity
        time_sim = self._time_similarity(
            event1.start_time, event1.end_time,
            event2.start_time, event2.end_time
        )
        similarity_factors.append(time_sim * 0.3)
        
        # Location similarity
        location_sim = self._text_similarity(
            event1.location or "", event2.location or ""
        )
        similarity_factors.append(location_sim * 0.15)
        
        # Description similarity
        desc_sim = self._text_similarity(
            event1.description or "", event2.description or ""
        )
        similarity_factors.append(desc_sim * 0.15)
        
        return sum(similarity_factors)
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity using simple metrics"""
        if not text1 and not text2:
            return 1.0
        if not text1 or not text2:
            return 0.0
        
        # Simple Levenshtein-style similarity
        text1_lower = text1.lower()
        text2_lower = text2.lower()
        
        if text1_lower == text2_lower:
            return 1.0
        
        # Check for substring matches
        if text1_lower in text2_lower or text2_lower in text1_lower:
            return 0.8
        
        # Word-based similarity
        words1 = set(text1_lower.split())
        words2 = set(text2_lower.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def _time_similarity(
        self,
        start1: datetime, end1: datetime,
        start2: datetime, end2: datetime
    ) -> float:
        """Calculate time overlap similarity"""
        if not all([start1, end1, start2, end2]):
            return 0.0
        
        # Calculate overlap
        overlap_start = max(start1, start2)
        overlap_end = min(end1, end2)
        
        if overlap_start >= overlap_end:
            return 0.0
        
        overlap_duration = (overlap_end - overlap_start).total_seconds()
        event1_duration = (end1 - start1).total_seconds()
        event2_duration = (end2 - start2).total_seconds()
        
        # Calculate similarity as overlap ratio
        max_duration = max(event1_duration, event2_duration)
        if max_duration == 0:
            return 1.0
        
        return overlap_duration / max_duration
    
    async def _detect_title_conflicts(
        self, 
        source_event: CalendarEvent, 
        destination_event: CalendarEvent
    ) -> List[FieldConflict]:
        """Detect title conflicts"""
        conflicts = []
        
        source_title = source_event.title or ""
        dest_title = destination_event.title or ""
        
        if source_title != dest_title:
            similarity = self._text_similarity(source_title, dest_title)
            
            conflict_type = FieldConflictType.VALUE_MISMATCH
            if not source_title or not dest_title:
                conflict_type = FieldConflictType.PRESENCE_MISMATCH
            
            conflicts.append(FieldConflict(
                field_name="title",
                conflict_type=conflict_type,
                source_value=source_title,
                destination_value=dest_title,
                source_provider=source_event.provider.value if source_event.provider else "unknown",
                destination_provider=destination_event.provider.value if destination_event.provider else "unknown",
                confidence_score=1.0 - similarity,
                resolution_suggestion="Use longer/more descriptive title" if len(source_title) != len(dest_title) else None
            ))
        
        return conflicts
    
    async def _detect_time_conflicts(
        self,
        source_event: CalendarEvent,
        destination_event: CalendarEvent
    ) -> List[FieldConflict]:
        """Detect time-related conflicts"""
        conflicts = []
        
        # Start time conflicts
        if source_event.start_time != destination_event.start_time:
            time_diff = abs((source_event.start_time - destination_event.start_time).total_seconds())
            
            conflicts.append(FieldConflict(
                field_name="start_time",
                conflict_type=FieldConflictType.VALUE_MISMATCH,
                source_value=source_event.start_time.isoformat(),
                destination_value=destination_event.start_time.isoformat(),
                source_provider=source_event.provider.value if source_event.provider else "unknown",
                destination_provider=destination_event.provider.value if destination_event.provider else "unknown",
                confidence_score=min(1.0, time_diff / 3600.0),  # Higher confidence for larger differences
                resolution_suggestion="Check timezone differences" if time_diff % 3600 == 0 else None
            ))
        
        # End time conflicts
        if source_event.end_time != destination_event.end_time:
            time_diff = abs((source_event.end_time - destination_event.end_time).total_seconds())
            
            conflicts.append(FieldConflict(
                field_name="end_time",
                conflict_type=FieldConflictType.VALUE_MISMATCH,
                source_value=source_event.end_time.isoformat(),
                destination_value=destination_event.end_time.isoformat(),
                source_provider=source_event.provider.value if source_event.provider else "unknown",
                destination_provider=destination_event.provider.value if destination_event.provider else "unknown",
                confidence_score=min(1.0, time_diff / 3600.0),
                resolution_suggestion="Check timezone differences" if time_diff % 3600 == 0 else None
            ))
        
        return conflicts
    
    async def _detect_location_conflicts(
        self,
        source_event: CalendarEvent,
        destination_event: CalendarEvent
    ) -> List[FieldConflict]:
        """Detect location conflicts"""
        conflicts = []
        
        source_location = source_event.location or ""
        dest_location = destination_event.location or ""
        
        if source_location != dest_location:
            similarity = self._text_similarity(source_location, dest_location)
            
            conflict_type = FieldConflictType.VALUE_MISMATCH
            if not source_location or not dest_location:
                conflict_type = FieldConflictType.PRESENCE_MISMATCH
            
            conflicts.append(FieldConflict(
                field_name="location",
                conflict_type=conflict_type,
                source_value=source_location,
                destination_value=dest_location,
                source_provider=source_event.provider.value if source_event.provider else "unknown",
                destination_provider=destination_event.provider.value if destination_event.provider else "unknown",
                confidence_score=1.0 - similarity,
                resolution_suggestion="Normalize location formats" if similarity > 0.5 else None
            ))
        
        return conflicts
    
    async def _detect_description_conflicts(
        self,
        source_event: CalendarEvent,
        destination_event: CalendarEvent
    ) -> List[FieldConflict]:
        """Detect description conflicts"""
        conflicts = []
        
        source_desc = source_event.description or ""
        dest_desc = destination_event.description or ""
        
        if source_desc != dest_desc:
            similarity = self._text_similarity(source_desc, dest_desc)
            
            conflict_type = FieldConflictType.VALUE_MISMATCH
            if not source_desc or not dest_desc:
                conflict_type = FieldConflictType.PRESENCE_MISMATCH
            
            conflicts.append(FieldConflict(
                field_name="description",
                conflict_type=conflict_type,
                source_value=source_desc,
                destination_value=dest_desc,
                source_provider=source_event.provider.value if source_event.provider else "unknown",
                destination_provider=destination_event.provider.value if destination_event.provider else "unknown",
                confidence_score=1.0 - similarity,
                resolution_suggestion="Merge descriptions" if similarity > 0.3 else None
            ))
        
        return conflicts
    
    async def _detect_attendee_conflicts(
        self,
        source_event: CalendarEvent,
        destination_event: CalendarEvent
    ) -> List[FieldConflict]:
        """Detect attendee conflicts"""
        conflicts = []
        
        # For now, this is a placeholder as CalendarEvent doesn't have attendees field
        # This would be implemented when attendee support is added
        
        return conflicts
    
    async def _detect_recurrence_conflicts(
        self,
        source_event: CalendarEvent,
        destination_event: CalendarEvent
    ) -> List[FieldConflict]:
        """Detect recurrence pattern conflicts"""
        conflicts = []
        
        # Placeholder for recurrence conflict detection
        # Would check recurrence rules, exceptions, etc.
        
        return conflicts
    
    def _categorize_conflict(
        self, 
        field_conflicts: List[FieldConflict]
    ) -> Tuple[ConflictType, ConflictSeverity]:
        """Categorize conflict type and determine severity"""
        
        # Analyze field conflicts to determine overall conflict type
        field_names = [fc.field_name for fc in field_conflicts]
        
        if 'start_time' in field_names or 'end_time' in field_names:
            conflict_type = ConflictType.TIME_OVERLAP
        elif len(set(field_names)) == 1 and 'title' in field_names:
            conflict_type = ConflictType.DUPLICATE_CONTENT
        elif len(field_conflicts) > 3:
            conflict_type = ConflictType.METADATA_MISMATCH
        else:
            conflict_type = ConflictType.FIELD_LEVEL
        
        # Determine severity based on confidence scores and field importance
        max_confidence = max(fc.confidence_score for fc in field_conflicts)
        important_fields = ['title', 'start_time', 'end_time']
        has_important_conflicts = any(fc.field_name in important_fields for fc in field_conflicts)
        
        if max_confidence > 0.9 or (has_important_conflicts and max_confidence > 0.7):
            severity = ConflictSeverity.HIGH
        elif max_confidence > 0.6 or has_important_conflicts:
            severity = ConflictSeverity.MEDIUM
        else:
            severity = ConflictSeverity.LOW
        
        return conflict_type, severity
    
    def _calculate_resolution_deadline(self, severity: ConflictSeverity) -> datetime:
        """Calculate when a conflict should be resolved by"""
        base_time = datetime.utcnow()
        
        if severity == ConflictSeverity.CRITICAL:
            return base_time + timedelta(hours=1)
        elif severity == ConflictSeverity.HIGH:
            return base_time + timedelta(hours=6)
        elif severity == ConflictSeverity.MEDIUM:
            return base_time + timedelta(days=1)
        else:
            return base_time + timedelta(days=7)


class ConflictResolver:
    """Resolves conflicts using various strategies"""
    
    def __init__(self, storage_manager: SyncStorageManager):
        self.storage = storage_manager
        self.resolution_strategies = {
            ConflictResolution.SOURCE_WINS: self._resolve_source_wins,
            ConflictResolution.DESTINATION_WINS: self._resolve_destination_wins,
            ConflictResolution.LATEST_WINS: self._resolve_latest_wins,
            ConflictResolution.MANUAL: self._resolve_manual
        }
    
    async def resolve_conflict(
        self,
        conflict: SyncConflict,
        strategy: ConflictResolution,
        user_id: Optional[str] = None
    ) -> ConflictResolutionResult:
        """
        Resolve a conflict using the specified strategy
        
        Args:
            conflict: The conflict to resolve
            strategy: Resolution strategy to use
            user_id: ID of user making manual resolution (if applicable)
            
        Returns:
            ConflictResolutionResult with resolved event and metadata
        """
        
        resolver_func = self.resolution_strategies.get(strategy)
        if not resolver_func:
            raise ValueError(f"Unknown resolution strategy: {strategy}")
        
        try:
            result = await resolver_func(conflict)
            
            # Mark conflict as resolved
            conflict.is_resolved = True
            conflict.resolution_result = result
            conflict.resolved_by = user_id or "system"
            conflict.resolved_at = datetime.utcnow()
            
            # Store conflict resolution for learning
            await self._store_conflict_resolution(conflict)
            
            return result
        
        except Exception as e:
            logger.error(f"Error resolving conflict {conflict.id}: {e}")
            raise
    
    async def _resolve_source_wins(self, conflict: SyncConflict) -> ConflictResolutionResult:
        """Source calendar event takes precedence"""
        
        field_resolutions = {}
        for field_conflict in conflict.field_conflicts:
            field_resolutions[field_conflict.field_name] = "source"
        
        return ConflictResolutionResult(
            resolved_event=conflict.source_event,
            resolution_strategy_used=ConflictResolution.SOURCE_WINS,
            field_resolutions=field_resolutions,
            confidence_score=1.0,
            resolution_notes=["Source event chosen due to SOURCE_WINS strategy"]
        )
    
    async def _resolve_destination_wins(self, conflict: SyncConflict) -> ConflictResolutionResult:
        """Destination calendar event takes precedence"""
        
        field_resolutions = {}
        for field_conflict in conflict.field_conflicts:
            field_resolutions[field_conflict.field_name] = "destination"
        
        return ConflictResolutionResult(
            resolved_event=conflict.destination_event,
            resolution_strategy_used=ConflictResolution.DESTINATION_WINS,
            field_resolutions=field_resolutions,
            confidence_score=1.0,
            resolution_notes=["Destination event chosen due to DESTINATION_WINS strategy"]
        )
    
    async def _resolve_latest_wins(self, conflict: SyncConflict) -> ConflictResolutionResult:
        """Most recently modified event takes precedence"""
        
        source_time = (conflict.source_event.updated_at or 
                      conflict.source_event.created_at or 
                      datetime.min)
        dest_time = (conflict.destination_event.updated_at or 
                    conflict.destination_event.created_at or 
                    datetime.min)
        
        if source_time > dest_time:
            chosen_event = conflict.source_event
            chosen_source = "source"
        else:
            chosen_event = conflict.destination_event
            chosen_source = "destination"
        
        field_resolutions = {}
        for field_conflict in conflict.field_conflicts:
            field_resolutions[field_conflict.field_name] = chosen_source
        
        return ConflictResolutionResult(
            resolved_event=chosen_event,
            resolution_strategy_used=ConflictResolution.LATEST_WINS,
            field_resolutions=field_resolutions,
            confidence_score=0.8,
            resolution_notes=[
                f"Chose {chosen_source} event (modified: {source_time if chosen_source == 'source' else dest_time})"
            ]
        )
    
    async def _resolve_manual(self, conflict: SyncConflict) -> ConflictResolutionResult:
        """Manual resolution required - queue for user review"""
        
        return ConflictResolutionResult(
            resolved_event=conflict.destination_event,  # Keep existing until manual resolution
            resolution_strategy_used=ConflictResolution.MANUAL,
            field_resolutions={},
            confidence_score=0.0,
            requires_manual_review=True,
            resolution_notes=["Conflict queued for manual resolution"]
        )
    
    async def _store_conflict_resolution(self, conflict: SyncConflict):
        """Store conflict resolution for learning and audit purposes"""
        try:
            resolution_record = {
                "conflict_id": conflict.id,
                "conflict_type": conflict.conflict_type.value,
                "severity": conflict.severity.value,
                "strategy_used": conflict.resolution_result.resolution_strategy_used.value,
                "field_resolutions": conflict.resolution_result.field_resolutions,
                "confidence_score": conflict.resolution_result.confidence_score,
                "resolved_by": conflict.resolved_by,
                "resolved_at": conflict.resolved_at.isoformat() if conflict.resolved_at else None,
                "resolution_notes": conflict.resolution_result.resolution_notes
            }
            
            await self.storage.save_conflict_resolution(resolution_record)
            
        except Exception as e:
            logger.warning(f"Failed to store conflict resolution: {e}")


class ConflictManager:
    """Manages the overall conflict resolution process"""
    
    def __init__(self, storage_manager: SyncStorageManager):
        self.storage = storage_manager
        self.detector = ConflictDetector()
        self.resolver = ConflictResolver(storage_manager)
        self.active_conflicts: Dict[str, SyncConflict] = {}
    
    async def detect_and_resolve_conflicts(
        self,
        source_events: List[CalendarEvent],
        destination_events: List[CalendarEvent],
        default_strategy: ConflictResolution = ConflictResolution.LATEST_WINS
    ) -> List[ConflictResolutionResult]:
        """
        Detect and resolve conflicts between source and destination events
        
        Args:
            source_events: Events from source calendars
            destination_events: Events from destination calendar
            default_strategy: Default resolution strategy to use
            
        Returns:
            List of conflict resolution results
        """
        
        results = []
        
        # Create event lookup by similarity
        for source_event in source_events:
            for dest_event in destination_events:
                # Detect potential conflicts
                conflict = await self.detector.detect_conflicts(source_event, dest_event)
                
                if conflict:
                    # Store conflict for tracking
                    self.active_conflicts[conflict.id] = conflict
                    
                    # Resolve automatically if strategy allows
                    if (conflict.severity in [ConflictSeverity.LOW, ConflictSeverity.MEDIUM] or
                        default_strategy != ConflictResolution.MANUAL):
                        
                        resolution_result = await self.resolver.resolve_conflict(
                            conflict, default_strategy
                        )
                        results.append(resolution_result)
                    else:
                        # Queue for manual resolution
                        resolution_result = await self.resolver.resolve_conflict(
                            conflict, ConflictResolution.MANUAL
                        )
                        results.append(resolution_result)
        
        return results
    
    async def get_pending_conflicts(
        self, 
        severity_filter: Optional[ConflictSeverity] = None
    ) -> List[SyncConflict]:
        """Get conflicts pending manual resolution"""
        
        pending = []
        for conflict in self.active_conflicts.values():
            if not conflict.is_resolved:
                if severity_filter is None or conflict.severity == severity_filter:
                    pending.append(conflict)
        
        return pending
    
    async def resolve_conflict_manually(
        self,
        conflict_id: str,
        field_resolutions: Dict[str, str],
        user_id: str
    ) -> ConflictResolutionResult:
        """
        Manually resolve a conflict with specific field choices
        
        Args:
            conflict_id: ID of conflict to resolve
            field_resolutions: Dict mapping field names to "source"/"destination"/"custom"
            user_id: ID of user making the resolution
            
        Returns:
            ConflictResolutionResult with manually resolved event
        """
        
        conflict = self.active_conflicts.get(conflict_id)
        if not conflict:
            raise ValueError(f"Conflict {conflict_id} not found")
        
        if conflict.is_resolved:
            raise ValueError(f"Conflict {conflict_id} is already resolved")
        
        # Create resolved event based on field resolutions
        resolved_event = self._create_resolved_event(
            conflict.source_event,
            conflict.destination_event,
            field_resolutions
        )
        
        result = ConflictResolutionResult(
            resolved_event=resolved_event,
            resolution_strategy_used=ConflictResolution.MANUAL,
            field_resolutions=field_resolutions,
            confidence_score=1.0,  # Manual resolutions are high confidence
            resolution_notes=[f"Manually resolved by user {user_id}"]
        )
        
        # Mark conflict as resolved
        conflict.is_resolved = True
        conflict.resolution_result = result
        conflict.resolved_by = user_id
        conflict.resolved_at = datetime.utcnow()
        
        # Store resolution
        await self.resolver._store_conflict_resolution(conflict)
        
        return result
    
    def _create_resolved_event(
        self,
        source_event: CalendarEvent,
        destination_event: CalendarEvent,
        field_resolutions: Dict[str, str]
    ) -> CalendarEvent:
        """Create resolved event based on field-level choices"""
        
        # Start with source event as base
        resolved_event = CalendarEvent(
            id=source_event.id,
            title=source_event.title,
            description=source_event.description,
            start_time=source_event.start_time,
            end_time=source_event.end_time,
            location=source_event.location,
            all_day=source_event.all_day,
            provider=source_event.provider,
            calendar_id=source_event.calendar_id,
            provider_id=source_event.provider_id,
            created_at=source_event.created_at,
            updated_at=datetime.utcnow()
        )
        
        # Apply field-level resolutions
        for field_name, choice in field_resolutions.items():
            if choice == "destination":
                if hasattr(destination_event, field_name):
                    setattr(resolved_event, field_name, getattr(destination_event, field_name))
            elif choice == "source":
                # Already using source as base
                pass
            # "custom" values would need to be handled separately
        
        return resolved_event
    
    async def cleanup_resolved_conflicts(self, max_age_days: int = 30):
        """Clean up old resolved conflicts"""
        cutoff_time = datetime.utcnow() - timedelta(days=max_age_days)
        
        conflicts_to_remove = []
        for conflict_id, conflict in self.active_conflicts.items():
            if (conflict.is_resolved and 
                conflict.resolved_at and 
                conflict.resolved_at < cutoff_time):
                conflicts_to_remove.append(conflict_id)
        
        for conflict_id in conflicts_to_remove:
            del self.active_conflicts[conflict_id]
        
        logger.info(f"Cleaned up {len(conflicts_to_remove)} old resolved conflicts")
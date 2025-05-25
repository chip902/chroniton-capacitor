"""
Calendar Synchronization Architecture

This module defines the architecture for synchronizing calendars across different environments,
including isolated networks accessible only via VPN or Remote Desktop.

Architecture Overview:
---------------------

1. Central Calendar Service:
   - Main FastAPI microservice running on the Next.js application server
   - Manages authentication with calendar providers (Google, Microsoft)
   - Provides unified API for calendar operations
   - Maintains synchronization state and handles conflicts

2. Remote Calendar Agents:
   - Lightweight agents that run in isolated environments
   - Connect to local calendars or calendar services within their network
   - Securely transmit calendar data to the central service
   - Support various platforms: Python, Node.js, PowerShell, PowerAutomate

3. Synchronization Protocol:
   - REST-based communication protocol between agents and central service
   - WebSocket-based real-time updates when available
   - File-based synchronization for highly restricted environments
   - Message queue for reliable delivery in unstable network conditions

4. Security Model:
   - Encrypted communication using TLS
   - Token-based authentication for agents
   - Credential isolation (agents only have access to their own environment)
   - Optional end-to-end encryption for sensitive calendar data

5. Synchronization Flow:
   - Bidirectional sync between source calendars and unified calendar
   - Conflict resolution based on configurable rules
   - Incremental updates using delta tokens and sync markers
   - Periodic full synchronization for consistency checks
"""

from enum import Enum
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field
from datetime import datetime

class SyncDirection(str, Enum):
    """Direction of calendar synchronization"""
    READ_ONLY = "read_only"  # Only read from source calendar
    WRITE_ONLY = "write_only"  # Only write to source calendar
    BIDIRECTIONAL = "bidirectional"  # Read and write to source calendar

class SyncFrequency(str, Enum):
    """Frequency of calendar synchronization"""
    REAL_TIME = "real_time"  # Immediate sync when changes occur (webhook/push)
    HOURLY = "hourly"
    DAILY = "daily"
    MANUAL = "manual"

class SyncMethod(str, Enum):
    """Method used for calendar synchronization"""
    API = "api"  # Direct API integration
    AGENT = "agent"  # Remote agent in isolated environment
    FILE = "file"  # File-based sync (import/export)
    EMAIL = "email"  # Email-based sync for highly restricted environments

class ConflictResolution(str, Enum):
    """Strategy for resolving conflicts during synchronization"""
    SOURCE_WINS = "source_wins"  # Source calendar takes precedence
    DESTINATION_WINS = "destination_wins"  # Destination calendar takes precedence
    LATEST_WINS = "latest_wins"  # Most recently updated event wins
    MANUAL = "manual"  # Require manual resolution

class SyncSource(BaseModel):
    """Configuration for a calendar sync source"""
    id: str
    name: str
    provider_type: str  # google, microsoft, exchange, ical, custom, etc.
    connection_info: Dict[str, Any]
    credentials: Optional[Dict[str, Any]] = None
    sync_direction: SyncDirection = SyncDirection.READ_ONLY
    sync_frequency: SyncFrequency = SyncFrequency.HOURLY
    sync_method: SyncMethod = SyncMethod.API
    calendars: List[str] = Field(default_factory=list)  # List of calendar IDs to sync
    last_sync: Optional[datetime] = None
    sync_tokens: Dict[str, str] = Field(default_factory=dict)  # Tokens for incremental sync
    enabled: bool = True

class SyncDestination(BaseModel):
    """Configuration for a calendar sync destination"""
    id: str
    name: str
    provider_type: str  # google, microsoft, exchange, etc.
    connection_info: Dict[str, Any]
    credentials: Optional[Dict[str, Any]] = None
    calendar_id: str  # Primary destination calendar ID
    conflict_resolution: ConflictResolution = ConflictResolution.LATEST_WINS
    categories: Dict[str, str] = Field(default_factory=dict)  # Mapping source -> category
    # New fields for multiple calendars and color management
    source_calendars: Dict[str, str] = Field(default_factory=dict)  # Mapping source_id -> calendar_id
    color_management: str = "separate_calendar"  # Options: "category", "property", "separate_calendar"

class SyncAgentConfig(BaseModel):
    """Configuration for a remote calendar sync agent"""
    id: str
    name: str
    environment: str  # Description of isolated environment
    agent_type: str  # python, node, powershell, powerautomate
    sources: List[SyncSource] = Field(default_factory=list)
    communication_method: SyncMethod
    api_endpoint: Optional[str] = None  # For API-based agents
    file_path: Optional[str] = None  # For file-based agents
    email_address: Optional[str] = None  # For email-based agents
    auth_token: Optional[str] = None
    interval_minutes: int = 60
    last_check_in: Optional[datetime] = None
    enabled: bool = True

class SyncConfiguration(BaseModel):
    """Master configuration for calendar synchronization"""
    sources: List[SyncSource] = Field(default_factory=list)
    destination: SyncDestination
    agents: List[SyncAgentConfig] = Field(default_factory=list)
    global_settings: Dict[str, Any] = Field(default_factory=dict)
"""
Enhanced Sync Token Management System

This module implements persistent sync token storage with validation, refresh
capabilities, and intelligent fallback to full sync when tokens are invalid.
Provider-specific token handling with cleanup and maintenance routines.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
import json
from uuid import uuid4

from services.calendar_event import CalendarProvider
from sync.storage import SyncStorageManager

logger = logging.getLogger(__name__)


class TokenType(str, Enum):
    """Types of sync tokens"""
    SYNC_TOKEN = "sync_token"           # Google nextSyncToken
    DELTA_LINK = "delta_link"           # Microsoft deltaLink  
    CHANGE_KEY = "change_key"           # Exchange changeKey
    ETAG = "etag"                       # Generic ETag
    LAST_MODIFIED = "last_modified"     # Timestamp-based sync
    CUSTOM = "custom"                   # Provider-specific token


class TokenStatus(str, Enum):
    """Status of sync tokens"""
    VALID = "valid"                     # Token is valid and usable
    EXPIRED = "expired"                 # Token has expired
    INVALID = "invalid"                 # Token format is invalid
    CORRUPTED = "corrupted"             # Token data is corrupted
    RATE_LIMITED = "rate_limited"       # Token usage rate limited
    REVOKED = "revoked"                 # Token has been revoked


@dataclass
class TokenMetadata:
    """Metadata associated with sync tokens"""
    created_at: datetime
    last_used: datetime
    last_validated: datetime
    usage_count: int = 0
    validation_failures: int = 0
    rate_limit_reset: Optional[datetime] = None
    provider_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SyncToken:
    """Represents a synchronization token with metadata"""
    id: str
    provider: CalendarProvider
    calendar_id: str
    source_id: str
    token_type: TokenType
    token_value: str
    status: TokenStatus
    metadata: TokenMetadata
    expires_at: Optional[datetime] = None
    refresh_token: Optional[str] = None
    
    @property
    def is_expired(self) -> bool:
        """Check if token is expired"""
        if self.expires_at:
            return datetime.utcnow() >= self.expires_at
        return False
    
    @property
    def is_valid(self) -> bool:
        """Check if token is valid for use"""
        return (self.status == TokenStatus.VALID and 
                not self.is_expired and 
                self.metadata.validation_failures < 3)
    
    @property
    def needs_refresh(self) -> bool:
        """Check if token needs refresh"""
        if not self.expires_at:
            return False
        
        # Refresh if expires within 10 minutes
        return datetime.utcnow() >= (self.expires_at - timedelta(minutes=10))
    
    def update_usage(self):
        """Update token usage statistics"""
        self.metadata.last_used = datetime.utcnow()
        self.metadata.usage_count += 1
    
    def mark_validation_failure(self):
        """Mark a validation failure"""
        self.metadata.validation_failures += 1
        
        if self.metadata.validation_failures >= 3:
            self.status = TokenStatus.INVALID
            logger.warning(f"Token {self.id} marked as invalid due to repeated failures")
    
    def reset_validation_failures(self):
        """Reset validation failure count"""
        self.metadata.validation_failures = 0
        self.metadata.last_validated = datetime.utcnow()
        if self.status == TokenStatus.INVALID:
            self.status = TokenStatus.VALID


class TokenValidator:
    """Validates sync tokens against provider APIs"""
    
    def __init__(self, unified_service):
        self.unified_service = unified_service
        self.validation_cache: Dict[str, Tuple[datetime, bool]] = {}
        self.cache_ttl = timedelta(minutes=5)
    
    async def validate_token(self, token: SyncToken) -> bool:
        """
        Validate a sync token against the provider API
        
        Args:
            token: SyncToken to validate
            
        Returns:
            True if token is valid, False otherwise
        """
        
        # Check cache first
        cache_key = f"{token.provider.value}:{token.calendar_id}:{token.token_value[:10]}"
        if cache_key in self.validation_cache:
            cached_time, cached_result = self.validation_cache[cache_key]
            if datetime.utcnow() - cached_time < self.cache_ttl:
                return cached_result
        
        try:
            is_valid = await self._validate_provider_token(token)
            
            # Update cache
            self.validation_cache[cache_key] = (datetime.utcnow(), is_valid)
            
            # Update token status
            if is_valid:
                token.reset_validation_failures()
            else:
                token.mark_validation_failure()
            
            return is_valid
        
        except Exception as e:
            logger.error(f"Error validating token {token.id}: {e}")
            token.mark_validation_failure()
            return False
    
    async def _validate_provider_token(self, token: SyncToken) -> bool:
        """Validate token with specific provider"""
        
        try:
            if token.provider == CalendarProvider.GOOGLE:
                return await self._validate_google_token(token)
            elif token.provider == CalendarProvider.MICROSOFT:
                return await self._validate_microsoft_token(token)
            elif token.provider == CalendarProvider.EXCHANGE:
                return await self._validate_exchange_token(token)
            else:
                logger.warning(f"No validator for provider {token.provider}")
                return True  # Assume valid if no specific validator
        
        except Exception as e:
            logger.error(f"Provider validation error for {token.provider}: {e}")
            return False
    
    async def _validate_google_token(self, token: SyncToken) -> bool:
        """Validate Google Calendar sync token"""
        try:
            # Try to use the token in a minimal API call
            # This is a simplified validation - in production, you might use
            # the token in an actual sync request to see if it works
            
            # For now, basic format validation
            if token.token_type == TokenType.SYNC_TOKEN:
                # Google sync tokens are typically long strings
                return len(token.token_value) > 10 and token.token_value.isalnum()
            
            return True
        
        except Exception:
            return False
    
    async def _validate_microsoft_token(self, token: SyncToken) -> bool:
        """Validate Microsoft Graph delta link"""
        try:
            if token.token_type == TokenType.DELTA_LINK:
                # Delta links are URLs
                return token.token_value.startswith('https://graph.microsoft.com')
            
            return True
        
        except Exception:
            return False
    
    async def _validate_exchange_token(self, token: SyncToken) -> bool:
        """Validate Exchange sync token"""
        try:
            # Exchange uses change keys or watermarks
            return len(token.token_value) > 5
        
        except Exception:
            return False


class TokenRefresher:
    """Handles token refresh operations"""
    
    def __init__(self, unified_service, storage_manager: SyncStorageManager):
        self.unified_service = unified_service
        self.storage = storage_manager
    
    async def refresh_token(self, token: SyncToken) -> Optional[SyncToken]:
        """
        Refresh an expired or expiring token
        
        Args:
            token: Token to refresh
            
        Returns:
            New token if refresh successful, None otherwise
        """
        
        try:
            if token.provider == CalendarProvider.GOOGLE:
                return await self._refresh_google_token(token)
            elif token.provider == CalendarProvider.MICROSOFT:
                return await self._refresh_microsoft_token(token)
            else:
                logger.warning(f"No refresh method for provider {token.provider}")
                return None
        
        except Exception as e:
            logger.error(f"Error refreshing token {token.id}: {e}")
            return None
    
    async def _refresh_google_token(self, token: SyncToken) -> Optional[SyncToken]:
        """Refresh Google Calendar token"""
        # Google sync tokens don't typically need refresh - they're obtained
        # during each sync operation. This would handle OAuth token refresh
        # if the sync token was tied to OAuth credentials
        
        return None  # Placeholder
    
    async def _refresh_microsoft_token(self, token: SyncToken) -> Optional[SyncToken]:
        """Refresh Microsoft Graph delta link"""
        # Similar to Google, delta links are typically refreshed during sync
        # This would handle OAuth token refresh for the underlying credentials
        
        return None  # Placeholder


class TokenManager:
    """Main sync token management system"""
    
    def __init__(self, storage_manager: SyncStorageManager, unified_service):
        self.storage = storage_manager
        self.unified_service = unified_service
        
        # Components
        self.validator = TokenValidator(unified_service)
        self.refresher = TokenRefresher(unified_service, storage_manager)
        
        # Token storage
        self.tokens: Dict[str, SyncToken] = {}
        self.provider_tokens: Dict[CalendarProvider, Dict[str, List[SyncToken]]] = {}
        
        # Maintenance
        self.cleanup_task: Optional[asyncio.Task] = None
        self.is_running = False
    
    async def initialize(self):
        """Initialize the token manager"""
        logger.info("Initializing sync token manager")
        
        # Load existing tokens from storage
        await self._load_tokens()
        
        # Start maintenance tasks
        await self.start_maintenance()
        
        logger.info(f"Token manager initialized with {len(self.tokens)} tokens")
    
    async def shutdown(self):
        """Shutdown the token manager"""
        logger.info("Shutting down sync token manager")
        
        # Stop maintenance tasks
        await self.stop_maintenance()
        
        # Save all tokens
        await self._save_all_tokens()
        
        logger.info("Token manager shut down")
    
    async def get_token(
        self, 
        provider: CalendarProvider, 
        calendar_id: str, 
        source_id: str
    ) -> Optional[SyncToken]:
        """
        Get a sync token for a specific calendar
        
        Args:
            provider: Calendar provider
            calendar_id: Calendar ID
            source_id: Sync source ID
            
        Returns:
            Valid SyncToken if available, None otherwise
        """
        
        # Look for existing token
        token_key = f"{provider.value}:{calendar_id}:{source_id}"
        token = self.tokens.get(token_key)
        
        if token:
            # Check if token is valid
            if token.is_valid:
                token.update_usage()
                return token
            
            # Try to refresh if needed and possible
            if token.needs_refresh and token.refresh_token:
                refreshed_token = await self.refresher.refresh_token(token)
                if refreshed_token:
                    await self.store_token(refreshed_token)
                    return refreshed_token
            
            # Validate token if it hasn't been validated recently
            if (datetime.utcnow() - token.metadata.last_validated).total_seconds() > 3600:
                is_valid = await self.validator.validate_token(token)
                if is_valid:
                    token.update_usage()
                    await self._save_token(token)
                    return token
        
        return None
    
    async def store_token(
        self,
        provider: CalendarProvider,
        calendar_id: str,
        source_id: str,
        token_type: TokenType,
        token_value: str,
        expires_at: Optional[datetime] = None,
        refresh_token: Optional[str] = None,
        provider_metadata: Optional[Dict[str, Any]] = None
    ) -> SyncToken:
        """
        Store a new sync token
        
        Args:
            provider: Calendar provider
            calendar_id: Calendar ID
            source_id: Sync source ID
            token_type: Type of token
            token_value: Token value
            expires_at: Optional expiration time
            refresh_token: Optional refresh token
            provider_metadata: Optional provider-specific metadata
            
        Returns:
            Created SyncToken
        """
        
        token_id = str(uuid4())
        token_key = f"{provider.value}:{calendar_id}:{source_id}"
        
        # Create token metadata
        metadata = TokenMetadata(
            created_at=datetime.utcnow(),
            last_used=datetime.utcnow(),
            last_validated=datetime.utcnow(),
            provider_metadata=provider_metadata or {}
        )
        
        # Create token
        token = SyncToken(
            id=token_id,
            provider=provider,
            calendar_id=calendar_id,
            source_id=source_id,
            token_type=token_type,
            token_value=token_value,
            status=TokenStatus.VALID,
            metadata=metadata,
            expires_at=expires_at,
            refresh_token=refresh_token
        )
        
        # Store token
        self.tokens[token_key] = token
        
        # Update provider index
        if provider not in self.provider_tokens:
            self.provider_tokens[provider] = {}
        if calendar_id not in self.provider_tokens[provider]:
            self.provider_tokens[provider][calendar_id] = []
        self.provider_tokens[provider][calendar_id].append(token)
        
        # Save to persistent storage
        await self._save_token(token)
        
        logger.info(f"Stored sync token {token_id} for {provider.value}:{calendar_id}")
        
        return token
    
    async def invalidate_token(
        self, 
        provider: CalendarProvider, 
        calendar_id: str, 
        source_id: str,
        reason: str = "manual_invalidation"
    ):
        """Invalidate a sync token"""
        
        token_key = f"{provider.value}:{calendar_id}:{source_id}"
        token = self.tokens.get(token_key)
        
        if token:
            token.status = TokenStatus.INVALID
            token.metadata.provider_metadata['invalidation_reason'] = reason
            
            await self._save_token(token)
            
            logger.info(f"Invalidated token {token.id}: {reason}")
    
    async def cleanup_expired_tokens(self):
        """Clean up expired and invalid tokens"""
        
        expired_count = 0
        invalid_count = 0
        
        tokens_to_remove = []
        for token_key, token in self.tokens.items():
            
            # Remove expired tokens
            if token.is_expired:
                tokens_to_remove.append(token_key)
                expired_count += 1
                continue
            
            # Remove invalid tokens with high failure count
            if (token.status == TokenStatus.INVALID and 
                token.metadata.validation_failures >= 5):
                tokens_to_remove.append(token_key)
                invalid_count += 1
                continue
            
            # Remove very old unused tokens
            if (datetime.utcnow() - token.metadata.last_used).days > 30:
                tokens_to_remove.append(token_key)
                continue
        
        # Remove tokens
        for token_key in tokens_to_remove:
            token = self.tokens.pop(token_key)
            await self._delete_token(token.id)
            
            # Update provider index
            provider_calendars = self.provider_tokens.get(token.provider, {})
            calendar_tokens = provider_calendars.get(token.calendar_id, [])
            if token in calendar_tokens:
                calendar_tokens.remove(token)
        
        if expired_count > 0 or invalid_count > 0:
            logger.info(f"Cleaned up {expired_count} expired and {invalid_count} invalid tokens")
    
    async def get_provider_statistics(self) -> Dict[str, Any]:
        """Get statistics about stored tokens"""
        
        stats = {
            'total_tokens': len(self.tokens),
            'by_provider': {},
            'by_status': {},
            'expired_tokens': 0,
            'tokens_needing_refresh': 0
        }
        
        # Count by provider
        for provider in CalendarProvider:
            provider_count = len([
                t for t in self.tokens.values() 
                if t.provider == provider
            ])
            if provider_count > 0:
                stats['by_provider'][provider.value] = provider_count
        
        # Count by status
        for status in TokenStatus:
            status_count = len([
                t for t in self.tokens.values() 
                if t.status == status
            ])
            if status_count > 0:
                stats['by_status'][status.value] = status_count
        
        # Count expired and needing refresh
        for token in self.tokens.values():
            if token.is_expired:
                stats['expired_tokens'] += 1
            if token.needs_refresh:
                stats['tokens_needing_refresh'] += 1
        
        return stats
    
    async def start_maintenance(self):
        """Start background maintenance tasks"""
        if not self.is_running:
            self.is_running = True
            self.cleanup_task = asyncio.create_task(self._maintenance_loop())
            logger.info("Started token maintenance tasks")
    
    async def stop_maintenance(self):
        """Stop background maintenance tasks"""
        self.is_running = False
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped token maintenance tasks")
    
    async def _maintenance_loop(self):
        """Background maintenance loop"""
        while self.is_running:
            try:
                # Run cleanup every hour
                await self.cleanup_expired_tokens()
                
                # Sleep for an hour
                await asyncio.sleep(3600)
                
            except Exception as e:
                logger.error(f"Error in token maintenance loop: {e}")
                await asyncio.sleep(300)  # Back off on errors
    
    async def _load_tokens(self):
        """Load tokens from persistent storage"""
        try:
            token_data = await self.storage.load_sync_tokens()
            
            for token_dict in token_data:
                try:
                    # Reconstruct token object
                    token = self._deserialize_token(token_dict)
                    
                    # Store in memory
                    token_key = f"{token.provider.value}:{token.calendar_id}:{token.source_id}"
                    self.tokens[token_key] = token
                    
                    # Update provider index
                    if token.provider not in self.provider_tokens:
                        self.provider_tokens[token.provider] = {}
                    if token.calendar_id not in self.provider_tokens[token.provider]:
                        self.provider_tokens[token.provider][token.calendar_id] = []
                    self.provider_tokens[token.provider][token.calendar_id].append(token)
                
                except Exception as e:
                    logger.error(f"Error deserializing token: {e}")
            
            logger.info(f"Loaded {len(self.tokens)} sync tokens from storage")
        
        except Exception as e:
            logger.error(f"Error loading tokens from storage: {e}")
    
    async def _save_token(self, token: SyncToken):
        """Save a single token to persistent storage"""
        try:
            token_dict = self._serialize_token(token)
            await self.storage.save_sync_token(token.id, token_dict)
        except Exception as e:
            logger.error(f"Error saving token {token.id}: {e}")
    
    async def _save_all_tokens(self):
        """Save all tokens to persistent storage"""
        try:
            token_data = []
            for token in self.tokens.values():
                token_dict = self._serialize_token(token)
                token_data.append(token_dict)
            
            await self.storage.bulk_save_sync_tokens(token_data)
            logger.info(f"Saved {len(token_data)} sync tokens to storage")
        
        except Exception as e:
            logger.error(f"Error saving all tokens: {e}")
    
    async def _delete_token(self, token_id: str):
        """Delete a token from persistent storage"""
        try:
            await self.storage.delete_sync_token(token_id)
        except Exception as e:
            logger.error(f"Error deleting token {token_id}: {e}")
    
    def _serialize_token(self, token: SyncToken) -> Dict[str, Any]:
        """Serialize token to dictionary for storage"""
        return {
            'id': token.id,
            'provider': token.provider.value,
            'calendar_id': token.calendar_id,
            'source_id': token.source_id,
            'token_type': token.token_type.value,
            'token_value': token.token_value,
            'status': token.status.value,
            'expires_at': token.expires_at.isoformat() if token.expires_at else None,
            'refresh_token': token.refresh_token,
            'metadata': {
                'created_at': token.metadata.created_at.isoformat(),
                'last_used': token.metadata.last_used.isoformat(),
                'last_validated': token.metadata.last_validated.isoformat(),
                'usage_count': token.metadata.usage_count,
                'validation_failures': token.metadata.validation_failures,
                'rate_limit_reset': token.metadata.rate_limit_reset.isoformat() if token.metadata.rate_limit_reset else None,
                'provider_metadata': token.metadata.provider_metadata
            }
        }
    
    def _deserialize_token(self, token_dict: Dict[str, Any]) -> SyncToken:
        """Deserialize token from dictionary"""
        metadata_dict = token_dict['metadata']
        
        metadata = TokenMetadata(
            created_at=datetime.fromisoformat(metadata_dict['created_at']),
            last_used=datetime.fromisoformat(metadata_dict['last_used']),
            last_validated=datetime.fromisoformat(metadata_dict['last_validated']),
            usage_count=metadata_dict.get('usage_count', 0),
            validation_failures=metadata_dict.get('validation_failures', 0),
            rate_limit_reset=datetime.fromisoformat(metadata_dict['rate_limit_reset']) if metadata_dict.get('rate_limit_reset') else None,
            provider_metadata=metadata_dict.get('provider_metadata', {})
        )
        
        return SyncToken(
            id=token_dict['id'],
            provider=CalendarProvider(token_dict['provider']),
            calendar_id=token_dict['calendar_id'],
            source_id=token_dict['source_id'],
            token_type=TokenType(token_dict['token_type']),
            token_value=token_dict['token_value'],
            status=TokenStatus(token_dict['status']),
            metadata=metadata,
            expires_at=datetime.fromisoformat(token_dict['expires_at']) if token_dict.get('expires_at') else None,
            refresh_token=token_dict.get('refresh_token')
        )
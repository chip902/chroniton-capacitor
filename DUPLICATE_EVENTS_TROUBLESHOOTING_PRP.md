# Duplicate Events Troubleshooting PRP (Problem Resolution Procedure)

## Problem Statement
**Issue**: Chroniton Capacitor OAuth sync is displaying 100+ identical calendar events with the same title, time, and date but different Google Calendar IDs.

**Symptoms**:
- Frontend calendar shows 100+ events with identical content ("Chip | Adobe Sync" at 12:30pm Sept 4)
- All events have same `source_id`, `calendar_name`, but different Google `id` fields
- User reports this is a **one-time meeting**, not a recurring event
- Events appear after OAuth sync succeeds

## Background Context
- **System**: Chroniton Capacitor calendar synchronization system
- **Frontend**: Chip Hosting Admin React app at `/Users/andrew/code/chip-hosting-admin/app/(main)/calendar/`
- **Backend**: FastAPI Python service at `/Users/andrew/code/chroniton-capacitor/`
- **OAuth Provider**: Google Calendar
- **Sync Method**: OAuth 2.0 with automatic sync source creation
- **Deployment**: Docker containers on ARK server (ark:8008)

## Investigation History

### Phase 1: Initial OAuth Issues (RESOLVED)
- **Problem**: OAuth codes failing with "invalid_grant" 500 errors
- **Root Cause**: OAuth callback tokens not being used automatically
- **Solution**: Modified `oauth_router.py` to auto-create sync sources from callback tokens

### Phase 2: Events Not Appearing (RESOLVED) 
- **Problem**: OAuth sync succeeded but frontend showed 0 events
- **Root Cause**: `/sync/events` endpoint only returned agent events, not OAuth sync source events
- **Solution**: Modified `sync_router.py` endpoints to include OAuth events via `controller._get_events_from_api_source()`

### Phase 3: CalendarEvent Conversion Error (RESOLVED)
- **Problem**: `'CalendarEvent' object does not support item assignment` 
- **Root Cause**: Trying to modify Pydantic model objects directly
- **Solution**: Convert `CalendarEvent` objects to dicts using `.dict()` method before modification

### Phase 4: Duplicate Events Issue (CURRENT)
- **Problem**: 100+ identical events appearing in frontend
- **Status**: Under investigation with debugging logs added
- **Hypothesis**: Google Calendar API returning expanded recurring event instances or duplicate API calls

## Current System Configuration

### OAuth Sync Sources
```bash
curl -s "http://ark:8008/sync/sources" | jq '.'
```
**Expected Output**: One source with 3 calendars:
- `andrew@chip-hosting.com` (primary)  
- `c_32df4c9cbd5f0f18217a19233b1ed2eea7327ad60b998346dcee74ccdc2a5495@group.calendar.google.com`
- `c_351ea807c3b9b130cb1dfc77e0f150333dce53f25b6162aec5739300efb99f53@group.calendar.google.com`

### Event Analysis Commands
```bash
# Total events count
curl -s "http://ark:8008/sync/events" | jq '.events | length'

# Event deduplication analysis  
curl -s "http://ark:8008/sync/events" | jq '.events | group_by(.title) | map({title: .[0].title, count: length})'

# Unique event IDs count
curl -s "http://ark:8008/sync/events" | jq '.events | map(.id) | unique | length'

# Sample event structure
curl -s "http://ark:8008/sync/events" | jq '.events[0] | {title, source_id, calendar_name, id, start_time, end_time}'
```

## Debugging Implementation

### Added Logging Points
1. **sync_router.py line 995**: `logger.info(f"Got {len(source_events)} events from source {source.id} ({source.name})")`
2. **controller.py line 372**: `logger.info(f"Calendar {calendar_id}: got {len(calendar_events)} events")`
3. **google_calendar.py line 68**: Increased `max_results` from 100 → 2500

### Log Analysis Procedure
After deploying changes, monitor Docker logs during sync:
```bash
docker logs chroniton-capacitor-app-1 -f
```

**Expected Log Patterns**:
```
Calendar andrew@chip-hosting.com: got X events
Calendar c_32df...@group.calendar.google.com: got Y events  
Calendar c_351...@group.calendar.google.com: got Z events
Got 100 events from source google_oauth_default
```

## Troubleshooting Decision Tree

### Scenario A: One Calendar Returns 100+ Events
**Log Pattern**: `Calendar andrew@chip-hosting.com: got 100 events` (others show 0-few events)
**Diagnosis**: Google Calendar API bug or data issue in primary calendar
**Actions**:
1. Check Google Calendar directly for recurring events
2. Verify `singleEvents: True` parameter behavior
3. Add event deduplication logic in controller
4. Consider filtering by date range

### Scenario B: Same Event Across Multiple Calendars
**Log Pattern**: Multiple calendars show same event counts, sum equals 100
**Diagnosis**: Shared/invited event appearing in multiple calendars
**Actions**:
1. Implement event deduplication by Google ID
2. Add calendar priority filtering
3. Check event attendee/organizer fields

### Scenario C: Multiple Sync Calls
**Log Pattern**: Same calendar logged multiple times per request
**Diagnosis**: Sync method being called repeatedly
**Actions**:
1. Add request tracking/caching
2. Check for multiple frontend calls
3. Implement request deduplication

### Scenario D: Google API Pagination Issue
**Log Pattern**: Normal event counts but still 100 duplicates
**Diagnosis**: API pagination or sync token issues
**Actions**:
1. Check `nextSyncToken` handling
2. Verify pagination parameters
3. Clear sync tokens and re-sync

## Implementation Files

### Key Files Modified
- `/Users/andrew/code/chroniton-capacitor/src/api/sync_router.py` - Events endpoints
- `/Users/andrew/code/chroniton-capacitor/src/api/oauth_router.py` - OAuth flow  
- `/Users/andrew/code/chroniton-capacitor/src/sync/controller.py` - Sync logic
- `/Users/andrew/code/chroniton-capacitor/src/services/google_calendar.py` - Google API calls
- `/Users/andrew/code/chip-hosting-admin/app/(main)/calendar/components/ChronitorCleanManager.tsx` - Frontend OAuth UI

### Critical Code Sections

#### Event Retrieval (sync_router.py:993-1008)
```python
source_events = await controller._get_events_from_api_source(source)
logger.info(f"Got {len(source_events)} events from source {source.id} ({source.name})")
for event in source_events:
    if hasattr(event, 'dict'):
        event_copy = event.dict()
    # ... process event
```

#### Calendar Processing (controller.py:364-373)  
```python
result = await self.unified_service.google_service.get_events(
    token_info=source.credentials,
    calendar_id=calendar_id,
    start_date=start_date,
    end_date=end_date,
    sync_token=sync_token
)
calendar_events = result.get('events', [])
logger.info(f"Calendar {calendar_id}: got {len(calendar_events)} events")
events.extend(calendar_events)
```

## Resolution Strategies

### Immediate Fixes
1. **Event Deduplication**: Implement dedup by Google event ID
2. **Calendar Filtering**: Prioritize primary calendar only  
3. **Date Range Limiting**: Reduce sync window from 90 to 30 days
4. **Max Results Tuning**: Adjust per-calendar limits

### Long-term Solutions
1. **Intelligent Sync**: Skip calendars with excessive event counts
2. **Event Fingerprinting**: Dedupe by title+time+location hash
3. **Sync Optimization**: Implement incremental sync tokens properly
4. **User Controls**: Allow calendar selection in frontend

## Testing Protocol

### Validation Steps
1. Deploy debugging version to ARK
2. Clear existing events: `curl -X DELETE "http://ark:8008/sync/events/google_oauth_default"`
3. Trigger fresh sync via frontend "Sync Now" button
4. Analyze logs for duplication patterns
5. Verify frontend event count and diversity
6. Test with different date ranges

### Success Criteria
- ✅ Events sync successfully (no errors)
- ✅ Reasonable event count (< 50 per calendar expected)
- ✅ Event diversity (multiple different events, not just one repeated)
- ✅ Correct event details (title, time, location)
- ✅ Last sync timestamp updates in UI

## Escalation Path
If issue persists after debugging:
1. **Google Calendar API Support** - Report potential API bug
2. **Data Analysis** - Export raw API responses for analysis
3. **Alternative Approach** - Consider CalDAV or different sync strategy
4. **User Workaround** - Temporary single-calendar sync option

## Execution Instructions for Agent

### Prerequisites
- Access to `/Users/andrew/code/chroniton-capacitor/` codebase
- Docker deployment capability to ARK server
- Ability to monitor Docker logs and make API calls

### Step-by-Step Execution
1. **Deploy Current Debugging Version**
   ```bash
   cd /Users/andrew/code/chroniton-capacitor
   git pull  # Ensure latest debugging code (commit 888eb8d)
   # User deploys to ARK server
   ```

2. **Monitor Sync Execution**
   ```bash
   # Watch logs during sync
   docker logs chroniton-capacitor-app-1 -f
   
   # Trigger sync via API or frontend
   curl -X POST "http://ark:8008/sync/run"
   ```

3. **Analyze Log Output**
   - Record event counts per calendar
   - Note total events from source
   - Identify duplication pattern

4. **Apply Appropriate Fix Based on Findings**
   - Refer to Decision Tree above
   - Implement targeted solution
   - Test and validate

5. **Document Resolution**
   - Update this PRP with findings
   - Record final solution implemented
   - Create prevention measures

---

**Document Version**: 1.0  
**Created**: 2025-09-02  
**Last Updated**: 2025-09-02  
**Status**: Active Investigation
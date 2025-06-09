# Advanced Calendar Synchronization System

This comprehensive sync system supports multiple platforms and calendar providers, with breakthrough support for Outlook for Mac. Consolidates calendars from isolated networks into unified destinations like Google Workspace.

## 🌟 New Features

### Outlook for Mac - OLK15EventParser
- ✅ **Bypasses Microsoft's anti-scraping measures** - Direct .olk15Event file processing
- ✅ **Processes 9,000+ events efficiently** - Tested with real-world datasets  
- ✅ **256+ account directory discovery** - Comprehensive calendar coverage
- ✅ **Google Workspace integration** - Direct sync to Google Calendar destinations

### Enhanced Master Server
- ✅ **Agent heartbeat system** - Reliable event collection and transmission
- ✅ **Google OAuth2 integration** - Streamlined Google Calendar setup
- ✅ **Event processing pipeline** - Normalizes and syncs events from agents
- ✅ **End-to-end testing** - Built-in sync verification endpoints

## Quick Start

### For Outlook for Mac (Enhanced with OLK15EventParser)

1. **On your Mac with Outlook for Mac**:
   ```bash
   # Download the enhanced agent
   cd /opt/calendar-agent/
   curl -O http://your-server:8008/src/sync/remote_agent.py
   curl -O http://your-server:8008/src/sync/OLK15EventParser.py
   
   # Install Python dependencies
   pip install plistlib pathlib logging
   ```

2. **Automatic discovery and configuration**:
   ```bash
   # Run discovery mode to find all calendars
   python remote_agent.py --mode discover
   
   # This automatically:
   # - Finds all .olk15Event files in 256+ account directories
   # - Processes 9,000+ events efficiently  
   # - Generates optimized outlook_config.json
   # - Configures Google Calendar destination
   ```

3. **Start syncing**:
   ```bash
   # Start the enhanced agent
   python remote_agent.py
   
   # Monitor real-time sync
   tail -f calendar_agent.log
   ```

### For Windows Outlook (Traditional COM Interface)

1. **On your Windows machine with Outlook**:
   - Download and install Python from [python.org](https://www.python.org/downloads/)
   - Copy agent files: `remote_agent.py`, `outlook_config.json`, `run_agent.bat`

2. **Edit the config file**:
   ```json
   {
     "central_api_url": "http://your-central-server:8008",
     "calendar_sources": [
       {
         "type": "outlook",
         "name": "Main Calendar",
         "calendar_name": "Calendar"
       }
     ]
   }
   ```

3. **Run the agent**:
   - Double-click `run_agent.bat`
   - Click "Allow" if Outlook asks for permission

### For Google Calendar Destinations

1. **Configure Google Calendar destination**:
   ```bash
   # Get authorization URL
   curl http://your-server:8008/sync/config/google/auth-url
   
   # Visit URL, authorize, get code
   # Exchange code for tokens
   curl -X POST http://your-server:8008/sync/config/google/exchange-code \
     -d '{"code": "your-auth-code"}'
   
   # Configure destination
   curl -X POST http://your-server:8008/sync/config/destination/google \
     -d '{"credentials": {"access_token": "...", "refresh_token": "..."}}'
   ```

2. **Test end-to-end sync**:
   ```bash
   curl -X POST http://your-server:8008/sync/test/end-to-end
   ```

## Configuration Options

### Sync Multiple Calendars

To sync more than one Outlook calendar, edit the `calendar_sources` section:

```json
"calendar_sources": [
  {
    "type": "outlook",
    "name": "Main Calendar",
    "calendar_name": "Calendar"
  },
  {
    "type": "outlook",
    "name": "Work Calendar",
    "calendar_name": "Team Calendar"
  }
]
```

### Change Sync Frequency

To sync more or less often, change:
```json
"sync_interval_minutes": 30
```

## Auto-Start on Boot

To have the agent run automatically when Windows starts:

1. Right-click `run_agent.bat` and select "Create shortcut"
2. Press Win+R, type `shell:startup` and press Enter
3. Move the shortcut to this folder

## Troubleshooting

- **Can't find calendar**: Make sure the `calendar_name` in the config matches the name in Outlook exactly
- **Connection errors**: Check that your central server is running and accessible from the Windows machine
- **Sync not working**: Look in `calendar_agent.log` for detailed error messages

## Environment Configuration

### Remote Agent Configuration
No environment file needed for remote agents. Configuration is in `outlook_config.json`:

#### Enhanced Outlook Mac Agent Config:
```json
{
  "agent_id": "outlook-mac-agent",
  "agent_name": "Enhanced Outlook for Mac",
  "environment": "macOS",
  "central_api_url": "http://your-server:8008",
  "sync_interval_minutes": 30,
  "enable_olk15_parser": true,
  "max_events_per_heartbeat": 10000,
  "calendar_sources": [
    {
      "type": "outlook_mac",
      "name": "Work Calendar",
      "parser_mode": "olk15_files",
      "account_discovery": true
    }
  ]
}
```

### Master Server Environment (.env)
```bash
# Enhanced server settings
DEBUG=false
CORS_ORIGINS=http://localhost:3000,https://your-nextjs-app.com
API_PORT=8008

# Google Calendar Integration (NEW)
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://your-server:8008/auth/google/callback

# Redis for agent management
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=optional-redis-password

# Enhanced sync capabilities
ENABLE_OUTLOOK_MAC_PARSER=true
ENABLE_AGENT_EVENT_PROCESSING=true
MAX_EVENTS_PER_HEARTBEAT=10000
AGENT_HEARTBEAT_TIMEOUT=300

# Alternative destinations
# Microsoft Graph
MS_CLIENT_ID=your-client-id
MS_CLIENT_SECRET=your-client-secret
MS_REDIRECT_URI=http://your-server:8008/auth/microsoft/callback
MS_TENANT_ID=your-tenant-id

# Exchange/Mailcow
EXCHANGE_SERVER_URL=https://mail.yourdomain.com/ews/exchange.asmx
EXCHANGE_USERNAME=calendar@yourdomain.com
EXCHANGE_PASSWORD=your-password

# Sync settings
SYNC_INTERVAL_MINUTES=30
CONFLICT_RESOLUTION=latest_wins
```

## API Endpoints

### New Google Integration Endpoints
- `GET /sync/config/google/auth-url` - Get OAuth2 authorization URL
- `POST /sync/config/google/exchange-code` - Exchange auth code for tokens  
- `POST /sync/config/google/calendars` - List Google calendars
- `POST /sync/config/destination/google` - Configure Google destination

### Enhanced Agent Management
- `POST /sync/agents/{id}/heartbeat` - Enhanced heartbeat with event data
- `GET /sync/agents/{id}/status` - Agent status and event counts
- `POST /sync/test/end-to-end` - Test complete sync flow
- `GET /sync/stats` - Overall sync statistics

### Event Processing Pipeline
- Events collected via OLK15EventParser → Agent heartbeats → Master server
- Normalization via CalendarEvent.from_outlook_mac() 
- Destination sync via UnifiedCalendarService
- Real-time status tracking and error handling
# Bidirectional Calendar Sync System

A comprehensive master-agent calendar synchronization system with **full bidirectional sync capabilities**. Collects calendars from multiple isolated networks, consolidates them into a single destination, and enables real-time bidirectional updates across all connected calendars. Perfect for organizations with calendars scattered across different networks, VPNs, and Exchange servers.

## 🚀 New Features: Bidirectional Synchronization

**What's New**: This system now supports **full bidirectional calendar synchronization**, meaning changes made in your centralized master calendar will automatically propagate back to all remote agents and their local calendar sources.

### Key Capabilities:
- ✅ **Calendar Metadata Updates**: Rename, recolor, or modify calendar properties from anywhere
- ✅ **Real-time Change Propagation**: Updates flow both ways automatically
- ✅ **Multi-Provider Support**: Works with Google, Microsoft, Exchange, Outlook, and Apple calendars
- ✅ **Event Synchronization**: Create, update, and delete events from any endpoint
- ✅ **Conflict Resolution**: Intelligent handling of simultaneous changes
- ✅ **Reliable Delivery**: Queue-based system ensures no updates are lost

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                 CENTRALIZED MASTER SERVER                      │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │           BIDIRECTIONAL SYNC CONTROLLER                    │ │
│  │  • Receives updates from remote agents                     │ │
│  │  • Pushes changes to all connected agents                  │ │
│  │  • Manages update queues and conflict resolution          │ │
│  │  • Provides REST API and WebUI (port 8008)               │ │
│  │  • Connects to destination calendar (Mailcow/Exchange)   │ │
│  └─────────────────────────────────────────────────────────────┘ │
│              ↕ BIDIRECTIONAL HTTP API                           │
└─────────────────────────────────────────────────────────────────┘
                                   ↕
    ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
    │   REMOTE AGENT   │  │   REMOTE AGENT   │  │   REMOTE AGENT   │
    │  ┌──────────────┐ │  │  ┌──────────────┐ │  │  ┌──────────────┐ │
    │  │Windows PC #1 │ │  │  │Windows PC #2 │ │  │  │  VPN Network │ │
    │  │+ Outlook     │ │  │  │+ Exchange    │ │  │  │+ Google Cal  │ │
    │  │+ Local Cal   │ │  │  │+ Team Cals   │ │  │  │+ Apple Cal   │ │
    │  │↕ SYNC BOTH   │ │  │  │↕ SYNC BOTH   │ │  │  │↕ SYNC BOTH   │ │
    │  │  WAYS        │ │  │  │  WAYS        │ │  │  │  WAYS        │ │
    │  └──────────────┘ │  │  └──────────────┘ │  │  └──────────────┘ │
    └──────────────────┘  └──────────────────┘  └──────────────────┘
```

## How Bidirectional Sync Works

### The Complete Flow:

1. **📝 Change Made Anywhere**: User renames a calendar in Next.js frontend, Outlook, or any connected system
2. **📡 Central Processing**: Master server receives the change and validates it
3. **🔄 Smart Distribution**: Update is queued for all relevant remote agents
4. **⚡ Agent Processing**: Each agent receives updates during heartbeat checks
5. **🎯 Local Application**: Agents apply changes to their local calendar providers
6. **✅ Confirmation**: Agents confirm successful processing back to master
7. **🌐 Global Consistency**: All calendars across the network stay synchronized

### Example Scenario:
```
User renames "Work Calendar" → "Project Calendar" in Next.js app
     ↓
Master server receives PUT /calendars/{id} request
     ↓  
Update queued for agents: agent-office-pc, agent-vpn-network
     ↓
Agents check for updates during next heartbeat (every 30min)
     ↓
agent-office-pc applies rename to local Outlook calendar
agent-vpn-network applies rename to Exchange calendar
     ↓
Both agents confirm successful processing
     ↓
All calendars now show "Project Calendar" everywhere
```

## What Gets Deployed Where

### 🏢 MASTER SERVER (Your Centralized Office Server)
**Purpose**: Bidirectional sync hub that manages all calendar operations
**Deployment**: Single Docker container with Redis queue system

**Enhanced Capabilities**:
- **Receives calendar events** from remote agents
- **Pushes metadata changes** to all connected agents
- **Manages update queues** with Redis for reliability
- **Provides comprehensive REST API** for calendar management
- **Handles conflict resolution** for simultaneous changes
- **Connects to destination calendar** (Mailcow/Exchange/Google/etc.)

**What you need**:
- Docker and docker-compose
- Redis for update queue management
- Network access to your destination calendar server
- Port 8008 accessible to remote agents

### 📱 REMOTE AGENTS (Individual Computers/Networks)
**Purpose**: Bidirectional sync clients that both send and receive updates
**Deployment**: Enhanced Python script with bidirectional capabilities

**Enhanced Capabilities**:
- **Extract calendar data** from local sources (Outlook, Exchange, Google, etc.)
- **Send updates to master server** via heartbeat system
- **Receive and apply changes** from master server
- **Handle calendar metadata updates** (renames, color changes, etc.)
- **Confirm processing** of received updates
- **Support multiple calendar providers** in single agent

**What you need**:
- Python 3.8+ with required dependencies
- Network access to master server
- Credentials for local calendar sources
- Write permissions to local calendars

## Quick Start Guide

### Step 1: Deploy Master Server with Bidirectional Sync

1. **On your centralized office server**, clone this repository:
```bash
git clone <this-repo>
cd calendar_microservice
```

2. **Create environment configuration**:
```bash
cp .env.example .env
```

3. **Edit `.env` file** with enhanced configuration:
```bash
# Master server settings
DEBUG=false
CORS_ORIGINS=*

# Primary destination calendar (where all calendars consolidate)
EXCHANGE_SERVER_URL=https://192.168.1.50/ews/exchange.asmx
EXCHANGE_USERNAME=unified-calendar@yourdomain.com
EXCHANGE_PASSWORD=your-strong-password

# Redis for bidirectional sync queues (critical for reliability)
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=optional-redis-password

# API settings for bidirectional communication
API_PORT=8008
SYNC_INTERVAL_MINUTES=30
ENABLE_BIDIRECTIONAL_SYNC=true
UPDATE_QUEUE_RETENTION_DAYS=7

# Conflict resolution strategy
CONFLICT_RESOLUTION=latest_wins  # options: source_wins, destination_wins, latest_wins, manual
```

4. **Deploy with Docker**:
```bash
docker-compose up -d
```

5. **Verify bidirectional sync is enabled**:
```bash
curl http://your-office-server-ip:8008/health
curl http://your-office-server-ip:8008/sync/agents/status
```

### Step 2: Create Configuration Using Helper Scripts

**🎯 The Easy Way**: Use the automated discovery tools to create your `outlook_config.json` file automatically.

#### **For Windows with Outlook:**
1. **Download the discovery tool**:
```bash
# On Windows machine with Outlook
curl -O http://your-server:8008/src/sync/list_outlook_calendars.py
# OR copy from the repository: src/sync/list_outlook_calendars.py
```

2. **Run the discovery tool**:
```bash
cd C:\CalendarAgent\
python list_outlook_calendars.py
```

3. **The tool will automatically generate `outlook_config.json`** with all your Outlook calendars discovered and configured.

#### **For macOS with Outlook for Mac:**
1. **Download the smart discovery tool**:
```bash
# On macOS machine with Outlook for Mac
curl -O http://your-server:8008/src/sync/check_outlook_calendars.py
# OR copy from the repository: src/sync/check_outlook_calendars.py
```

2. **Configure your work domains** (edit the script first):
```python
# Edit check_outlook_calendars.py - Update line 19-20 with your domains
work_domains = ['yourcompany.com', 'yourdomain.org', 'company.net']
```

3. **Run the smart discovery**:
```bash
cd /opt/calendar-agent/
python check_outlook_calendars.py
```

4. **The tool will automatically**:
   - Find your Outlook database
   - Filter for work-related calendars
   - Generate optimized `outlook_config.json`
   - Skip personal/system calendars

#### **For macOS with Calendar app:**
1. **Download the Calendar app discovery tool**:
```bash
curl -O http://your-server:8008/src/sync/list_mac_calendars.py
```

2. **Run the discovery**:
```bash
python list_mac_calendars.py
```

3. **Use the generated configuration** snippets to create your `outlook_config.json`.

### 📋 Helper Script Examples and Outputs

#### **Windows Outlook Discovery Example:**

**Command:**
```bash
python list_outlook_calendars.py
```

**What you'll see:**
```
=== Outlook Calendar Configuration Helper ===

Searching for Outlook calendars...

Found 3 calendar(s):

1. Calendar
   Path: \\Personal Folders\Calendar
   Entry ID: 000000001A447390AA6611CD9BC800AA002FC45A0700...
   Items: 45 appointments
   Sample: Team Meeting at 2024-01-15 09:00:00

2. Work Projects  
   Path: \\Personal Folders\Work Projects
   Items: 23 appointments

3. Shared Team Calendar
   Path: \\Shared Calendars\Team Calendar
   Items: 67 appointments

=== Configuration Snippet ===
Copy this into your outlook_config.json:

{
  "agent_id": "windows-outlook-agent",
  "agent_name": "Windows Outlook Agent", 
  "environment": "Office Network",
  "central_api_url": "http://master-server:8008",
  "sync_interval_minutes": 30,
  "enable_bidirectional_sync": true,
  "calendar_sources": [
    {
      "type": "outlook",
      "name": "Calendar",
      "calendar_name": "Calendar",
      "calendar_id": "000000001A447390AA6611CD9BC800AA002FC45A0700...",
      "allow_metadata_updates": true
    },
    {
      "type": "outlook", 
      "name": "Work Projects",
      "calendar_name": "Work Projects",
      "calendar_id": "000000001A447390AA6611CD9BC800AA002FC45A0701...",
      "allow_metadata_updates": true
    },
    {
      "type": "outlook",
      "name": "Shared Team Calendar", 
      "calendar_name": "Team Calendar",
      "calendar_id": "000000001A447390AA6611CD9BC800AA002FC45A0702...",
      "allow_metadata_updates": false
    }
  ]
}

Full calendar details saved to: outlook_calendars_20240115_143022.json
```

#### **macOS Outlook Smart Discovery Example:**

**Command:**
```bash
python check_outlook_calendars.py
```

**What you'll see:**
```
=== Smart Outlook Mac Calendar Analysis ===

Looking for database at: ~/Library/Group Containers/.../Outlook.sqlite
✅ Found Outlook database

Getting calendar names from Outlook...
Found 2 calendar names from Outlook

Analyzing calendar data...
Found 5 calendar folders with events:
  - ID: 1, Events: 234, Email: john.doe@company.com
  - ID: 2, Events: 12, Email: john@gmail.com  
  - ID: 3, Events: 456, Email: team@company.com
  - ID: 4, Events: 8, Email: N/A (Holidays)
  - ID: 5, Events: 145, Email: sarah@company.com

Filtering for work calendars...
  - ✅ Including: ID 1 (john.doe@company.com)
  - ❌ Skipping non-work email: john@gmail.com
  - ✅ Including: ID 3 (team@company.com)  
  - ❌ Skipping system calendar: Holidays
  - ✅ Including: ID 5 (sarah@company.com)

✅ Configuration saved to outlook_config.json
Selected 3 calendars to sync:
  - Work Calendar (john.doe@company.com) (ID: 1)
  - Team Calendar (team@company.com) (ID: 3)
  - Sarah's Calendar (sarah@company.com) (ID: 5)
```

**Generated `outlook_config.json`:**
```json
{
  "agent_id": "outlook-mac-agent",
  "agent_name": "Outlook for Mac",
  "environment": "Local",
  "central_api_url": "http://localhost:8008",
  "sync_interval_minutes": 30,
  "enable_bidirectional_sync": true,
  "calendar_sources": [
    {
      "type": "outlook_mac",
      "name": "Work Calendar (john.doe@company.com)",
      "folder_id": "1",
      "account_uid": "1",
      "allow_metadata_updates": true
    },
    {
      "type": "outlook_mac",
      "name": "Team Calendar (team@company.com)",
      "folder_id": "3", 
      "account_uid": "2",
      "allow_metadata_updates": true
    },
    {
      "type": "outlook_mac",
      "name": "Sarah's Calendar (sarah@company.com)",
      "folder_id": "5",
      "account_uid": "3", 
      "allow_metadata_updates": true
    }
  ]
}
```

#### **macOS Calendar App Discovery Example:**

**Command:**
```bash
python list_mac_calendars.py
```

**What you'll see:**
```
=== macOS Calendar Configuration Helper ===

Searching for calendars in macOS Calendar app...

Found 4 calendar(s):

1. Home
   ID: 12345678-1234-1234-1234-123456789ABC
   Description: Personal calendar
   Events: 67

2. Work
   ID: 87654321-4321-4321-4321-CBA987654321  
   Events: 134

3. Holidays
   ID: ABCDEFGH-ABCD-ABCD-ABCD-ABCDEFGHIJKL
   Events: 52

4. Birthdays
   ID: IJKLMNOP-IJKL-IJKL-IJKL-IJKLMNOPQRST
   Events: 23

=== Configuration Snippet ===
Use this in your outlook_config.json (adjust as needed):

"calendar_sources": [
    {
        "type": "macos_calendar",
        "name": "Home",
        "calendar_name": "Home", 
        "calendar_id": "12345678-1234-1234-1234-123456789ABC",
        "allow_metadata_updates": true
    },
    {
        "type": "macos_calendar",
        "name": "Work",
        "calendar_name": "Work",
        "calendar_id": "87654321-4321-4321-4321-CBA987654321", 
        "allow_metadata_updates": true
    },
    {
        "type": "macos_calendar", 
        "name": "Holidays",
        "calendar_name": "Holidays",
        "calendar_id": "ABCDEFGH-ABCD-ABCD-ABCD-ABCDEFGHIJKL",
        "allow_metadata_updates": false
    }
]

Full calendar details saved to: macos_calendars_20240115_143022.json
```

### 🔧 Manual Configuration (Advanced Users)

If you prefer to create the configuration manually or need to customize further, create `outlook_config.json` with this structure:

```json
{
  "agent_id": "unique-agent-id",
  "agent_name": "Human Readable Name",
  "environment": "Network Description", 
  "central_api_url": "http://your-master-server:8008",
  "sync_interval_minutes": 30,
  "enable_bidirectional_sync": true,
  "calendar_sources": [
    {
      "type": "outlook|outlook_mac|macos_calendar|google|microsoft|exchange",
      "name": "Display Name",
      "calendar_name": "Calendar Name",
      "calendar_id": "calendar-identifier",
      "allow_metadata_updates": true,
      "allow_event_updates": true
    }
  ]
}
```

### 🐛 Helper Script Troubleshooting

#### **Windows Outlook Issues:**

**Problem**: `ImportError: No module named 'win32com.client'`
**Solution**:
```bash
pip install pywin32
# OR
conda install pywin32
```

**Problem**: `outlook.exe is not running` 
**Solution**:
```bash
# Start Outlook first, then run the script
start outlook
python list_outlook_calendars.py
```

**Problem**: `Permission denied accessing Outlook`
**Solution**:
- Run command prompt as Administrator
- Check Outlook security settings (File → Options → Trust Center)
- Enable programmatic access in Outlook security settings

#### **macOS Outlook Issues:**

**Problem**: `Could not find Outlook database`
**Solution**:
```bash
# 1. Make sure Outlook for Mac is installed and has been opened at least once
open -a "Microsoft Outlook"

# 2. Check if database exists manually
find ~/Library -name "*.sqlite" | grep -i outlook

# 3. Use the mdfind command provided by the script
mdfind -name '*.sqlite' | grep -i outlook

# 4. Check different Outlook versions
ls ~/Library/Group\ Containers/UBF8T346G9.Office/Outlook/
```

**Problem**: `sqlite3.OperationalError: database is locked`
**Solution**:
```bash
# Close Outlook for Mac completely before running the script
pkill -f "Microsoft Outlook"
python check_outlook_calendars.py
```

**Problem**: `No work calendars found`
**Solution**:
```python
# Edit the work_domains list in check_outlook_calendars.py (line 19-20)
work_domains = [
    'yourcompany.com',
    'yourdomain.org', 
    'company.net',
    'enterprise.com'
]
```

#### **macOS Calendar App Issues:**

**Problem**: `AppleScript execution error`
**Solution**:
```bash
# 1. Grant Terminal/Python permissions to control Calendar
# System Preferences → Security & Privacy → Privacy → Automation
# Enable Terminal/Python access to Calendar

# 2. Try running AppleScript directly to test
osascript -e 'tell application "Calendar" to get name of calendars'

# 3. Use alternative SQLite method if AppleScript fails
# The script automatically falls back to SQLite access
```

**Problem**: `Calendar app not responding`
**Solution**:
```bash
# Restart Calendar app
pkill -f "Calendar"
open -a "Calendar"
python list_mac_calendars.py
```

### 💡 Pro Tips for Helper Scripts

#### **Getting Better Results:**

1. **Run Outlook/Calendar apps first** before running discovery scripts
2. **Close other applications** that might be using calendar data
3. **Run as administrator/sudo** if you get permission errors
4. **Update your work domains** in the smart discovery script for better filtering
5. **Check the generated JSON files** for additional calendar details

#### **Customizing Work Domain Detection:**

Edit `check_outlook_calendars.py` to improve work calendar detection:

```python
# Lines 19-21: Add your organization's email domains
work_domains = [
    'company.com',
    'corporation.net', 
    'enterprise.org',
    'startup.io',
    'nonprofit.org'
]

# Lines 8-14: Adjust system calendar filtering
system_terms = [
    'holiday', 'birthday', 'holidays',
    'vacation', 'personal', 'private',
    'family', 'anniversary'
]
```

#### **Multiple Calendar Sources in One Agent:**

You can combine multiple calendar types in a single agent:

```json
{
  "agent_id": "multi-platform-agent",
  "calendar_sources": [
    {
      "type": "outlook_mac",
      "name": "Outlook Work Calendar",
      "folder_id": "1",
      "account_uid": "1"
    },
    {
      "type": "macos_calendar", 
      "name": "Personal Calendar",
      "calendar_id": "12345678-1234-1234-1234-123456789ABC"
    },
    {
      "type": "google",
      "name": "Google Work Calendar",
      "calendar_id": "primary",
      "credentials": {
        "client_id": "google-client-id",
        "refresh_token": "google-refresh-token"
      }
    }
  ]
}
```

### Step 3: Deploy Enhanced Remote Agents

For each computer/network with calendars you want to sync:

1. **On the target machine**, create a new folder (e.g., `C:\CalendarAgent\` or `/opt/calendar-agent/`)

2. **Copy the enhanced agent files**:
   - `src/sync/remote_agent.py` (now with bidirectional capabilities)
   - The `outlook_config.json` generated by the helper scripts
   - `src/sync/run_agent.bat` or `run_agent.sh`

3. **Install Python dependencies**:
```bash
# Windows
pip install aiohttp asyncio win32com python-dateutil

# Linux/Mac  
pip install aiohttp asyncio python-dateutil
```

4. **Your generated `outlook_config.json` will look like this**:
```json
{
  "agent_id": "office-pc-main",
  "agent_name": "Main Office Computer",
  "environment": "Corporate Network",
  "central_api_url": "http://192.168.1.100:8008",
  "sync_interval_minutes": 30,
  "enable_bidirectional_sync": true,
  "calendar_sources": [
    {
      "type": "outlook",
      "name": "Primary Work Calendar",
      "calendar_name": "Calendar",
      "allow_metadata_updates": true,
      "allow_event_updates": true
    },
    {
      "type": "google",
      "name": "Google Calendar",
      "credentials": {
        "client_id": "your-google-client-id",
        "client_secret": "your-google-client-secret",
        "refresh_token": "your-refresh-token"
      },
      "calendar_id": "primary",
      "allow_metadata_updates": true
    },
    {
      "type": "exchange",
      "name": "Corporate Exchange",
      "exchange_url": "https://exchange.company.com/ews/exchange.asmx",
      "username": "user@company.com",
      "password": "secure-password",
      "allow_metadata_updates": false
    }
  ]
}
```

5. **Start the bidirectional agent**:
```bash
# Windows
run_agent.bat

# Linux/Mac
./run_agent.sh
```

6. **Verify bidirectional functionality**:
   - Check agent logs for "Bidirectional sync enabled"
   - Monitor heartbeat responses for pending updates
   - Test calendar rename from master server

### Step 3: Test Bidirectional Synchronization

#### Test Calendar Metadata Updates:

1. **From the master server API**:
```bash
# Rename a calendar
curl -X PUT "http://192.168.1.100:8008/calendars/calendar-id" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Updated Calendar Name", 
    "color": "#FF5733"
  }' \
  -G -d "provider=outlook" \
  -d "credentials={\"access_token\":\"token\"}"
```

2. **From Next.js frontend**:
```typescript
import { CalendarClient } from './CalendarClient';

const client = new CalendarClient('http://192.168.1.100:8008');

// Update calendar metadata
await client.updateCalendarMetadata('calendar-id', {
  name: 'New Calendar Name',
  color: '#00FF00'
}, 'outlook', credentials);
```

3. **Monitor propagation**:
```bash
# Check update queues
curl http://192.168.1.100:8008/sync/agents/office-pc-main/pending-updates

# Monitor agent logs
tail -f calendar_agent.log
```

## Bidirectional Sync Configuration

### Master Server Configuration

#### API Endpoints for Bidirectional Sync:

```yaml
# Calendar Management (CRUD operations)
PUT /calendars/{calendar_id}          # Update calendar metadata
POST /calendars                       # Create new calendar  
DELETE /calendars/{calendar_id}       # Delete calendar

# Bidirectional Push Operations
POST /sync/push/calendar-metadata     # Push metadata changes to agents
POST /sync/push/sync-config          # Push configuration updates
POST /sync/agents/{agent_id}/receive-updates  # Send direct updates

# Agent Communication
GET /sync/agents/{agent_id}/pending-updates   # Check pending updates
POST /sync/agents/{agent_id}/updates/{update_id}/processed  # Confirm processing
POST /sync/agents/{agent_id}/heartbeat        # Enhanced heartbeat with updates
```

#### Update Queue Management:

```python
# Redis queue structure for reliable delivery
sync:agent:{agent_id}:updates      # Hash of pending updates
sync:agent:{agent_id}:pending      # List of pending update IDs  
sync:agent:{agent_id}:processed    # Hash of processed updates (audit trail)
```

#### Conflict Resolution Strategies:

```bash
# Configure in .env
CONFLICT_RESOLUTION=latest_wins

# Available options:
# - source_wins: Remote agent changes take precedence
# - destination_wins: Master server changes take precedence  
# - latest_wins: Most recent timestamp wins
# - manual: Flag conflicts for manual resolution
```

### Remote Agent Configuration

#### Enhanced Agent Configuration:

```json
{
  "agent_id": "unique-agent-identifier",
  "agent_name": "Human-readable name", 
  "environment": "Network description",
  "central_api_url": "http://master-server:8008",
  "sync_interval_minutes": 30,
  "enable_bidirectional_sync": true,
  "update_processing_timeout": 300,
  "max_retry_attempts": 3,
  "calendar_sources": [
    {
      "type": "outlook|google|microsoft|exchange|apple",
      "name": "Display name for this calendar",
      "calendar_name": "Local calendar identifier",
      "allow_metadata_updates": true,
      "allow_event_updates": true,
      "conflict_resolution": "latest_wins",
      "credentials": {
        // Provider-specific authentication
      }
    }
  ]
}
```

#### Supported Calendar Providers:

**Outlook for Windows (COM Interface)**:
```json
{
  "type": "outlook",
  "name": "Outlook Calendar",
  "calendar_name": "Calendar",
  "allow_metadata_updates": true
}
```

**Outlook for Mac (SQLite Database)**:
```json
{
  "type": "outlook_mac",
  "name": "Outlook Mac Calendar",
  "calendar_name": "Calendar",
  "calendar_id": "calendar-identifier",
  "folder_id": "folder-id",
  "account_uid": "account-uid",
  "allow_metadata_updates": true
}
```

**Google Calendar (API)**:
```json
{
  "type": "google", 
  "name": "Google Calendar",
  "calendar_id": "primary",
  "credentials": {
    "client_id": "google-client-id",
    "client_secret": "google-client-secret", 
    "refresh_token": "google-refresh-token"
  },
  "allow_metadata_updates": true
}
```

**Microsoft Graph (Office 365)**:
```json
{
  "type": "microsoft",
  "name": "Office 365 Calendar",
  "calendar_id": "calendar-id",
  "credentials": {
    "tenant_id": "tenant-id",
    "client_id": "app-client-id",
    "client_secret": "app-secret"
  },
  "allow_metadata_updates": true
}
```

**Exchange Web Services**:
```json
{
  "type": "exchange",
  "name": "Exchange Calendar", 
  "exchange_url": "https://exchange.company.com/ews/exchange.asmx",
  "username": "user@company.com",
  "password": "password",
  "allow_metadata_updates": false
}
```

**Apple Calendar (macOS/iOS)**:
```json
{
  "type": "apple",
  "name": "Apple Calendar",
  "calendar_id": "calendar-uuid",
  "credentials": {
    "account_name": "iCloud",
    "username": "apple-id@icloud.com"
  },
  "allow_metadata_updates": true
}
```

**macOS Calendar (Built-in Calendar App)**:
```json
{
  "type": "macos_calendar",
  "name": "macOS Calendar",
  "calendar_name": "Calendar Name",
  "calendar_id": "calendar-uuid",
  "allow_metadata_updates": true
}
```

## Calendar Discovery and Configuration Tools

The system includes powerful discovery tools to automatically detect and configure calendars across different platforms. These tools simplify setup by finding all available calendars and generating appropriate configuration files.

### 🔍 Calendar Discovery Tools Overview

| Tool | Platform | Purpose | Output |
|------|----------|---------|---------|
| `list_outlook_calendars.py` | Windows | Discovers Outlook calendars via COM interface | Configuration snippets for Windows Outlook |
| `list_outlook_mac_calendars.py` | macOS | Discovers Outlook for Mac calendars via SQLite | Configuration snippets for Outlook on Mac |
| `list_mac_calendars.py` | macOS | Discovers macOS Calendar app calendars | Configuration snippets for macOS Calendar |
| `check_outlook_calendars.py` | macOS | Analyzes Outlook Mac calendars and filters work calendars | Smart configuration with work calendar detection |

### 🪟 Windows Outlook Calendar Discovery

**Purpose**: Automatically discovers all Outlook calendars on Windows using COM interface.

#### Usage:
```bash
# On Windows machine with Outlook
cd C:\CalendarAgent\
python list_outlook_calendars.py
```

#### What it does:
- **Connects to Outlook** via COM interface
- **Discovers all calendar folders** including shared and secondary calendars
- **Extracts calendar properties** (name, path, entry ID, store ID)
- **Counts appointments** in each calendar
- **Generates configuration snippets** ready for `outlook_config.json`

#### Sample Output:
```
=== Outlook Calendar Configuration Helper ===

Found 3 calendar(s):

1. Calendar
   Path: \\Personal Folders\Calendar
   Entry ID: 000000001A447390AA6611CD9BC800AA002FC45A0700...
   Store ID: 000000001A447390AA6611CD9BC800AA002FC45A0700...
   Items: 45 appointments
   Sample: Team Meeting at 2024-01-15 09:00:00

2. Work Projects
   Path: \\Personal Folders\Work Projects
   Entry ID: 000000001A447390AA6611CD9BC800AA002FC45A0701...
   Items: 23 appointments

=== Configuration Snippet ===
"calendar_sources": [
    {
        "type": "outlook",
        "name": "Calendar",
        "calendar_name": "Calendar",
        "calendar_id": "000000001A447390AA6611CD9BC800AA002FC45A0700...",
        "store_id": "000000001A447390AA6611CD9BC800AA002FC45A0700..."
    },
    ...
]
```

### 🍎 Outlook for Mac Calendar Discovery

**Purpose**: Discovers Outlook for Mac calendars by directly accessing the SQLite database.

#### Usage:
```bash
# On macOS with Outlook for Mac
cd /opt/calendar-agent/
python list_outlook_mac_calendars.py
```

#### Advanced Features:
- **Intelligent database discovery** - Searches multiple common Outlook database locations
- **Deep folder scanning** - Recursively searches for Outlook SQLite files
- **Database validation** - Verifies found databases contain calendar data
- **Account information extraction** - Gets account names and types
- **Event counting** - Counts events per calendar for better filtering

#### Database Search Paths:
```bash
# Primary search locations:
~/Library/Group Containers/UBF8T346G9.Office/Outlook/Outlook 15 Profiles/Main Profile/Data/
~/Library/Group Containers/UBF8T346G9.Office/Outlook/
~/Library/Containers/com.microsoft.Outlook/Data/Library/Application Support/Microsoft/Outlook/
~/Library/Application Support/Microsoft/Office/Outlook/
```

#### Sample Output:
```
=== Outlook for Mac Calendar Configuration Helper ===

Searching for Outlook database in common locations...
Found Outlook database at: /Users/.../Outlook.sqlite

Found 4 calendar(s):

1. Work Calendar
   ID: ABCD-1234-EFGH-5678
   Account: john.doe@company.com (Exchange)
   Events: 127
   Color: #FF5733

2. Personal
   ID: WXYZ-9876-STUV-5432
   Account: john@gmail.com (IMAP)
   Events: 45
   Color: #4285F4

=== Configuration Snippet ===
"calendar_sources": [
    {
        "type": "outlook_mac",
        "name": "Work Calendar",
        "calendar_name": "Work Calendar",
        "calendar_id": "ABCD-1234-EFGH-5678",
        "account": "john.doe@company.com"
    },
    ...
]
```

#### Troubleshooting:
If the database isn't found, the tool provides helpful guidance:
```
Could not find Outlook database. Here are some troubleshooting steps:
1. Make sure Outlook for Mac is installed and has been run at least once
2. Check if you have any Microsoft 365 or Exchange accounts added in Outlook
3. The database might be in a different location if you're using an older version
4. Try running 'mdfind -name '*.sqlite' | grep -i outlook' in Terminal
```

### 🍎 macOS Calendar App Discovery

**Purpose**: Discovers calendars from the built-in macOS Calendar application.

#### Usage:
```bash
# On macOS
cd /opt/calendar-agent/
python list_mac_calendars.py
```

#### Features:
- **AppleScript integration** - Uses AppleScript to query Calendar app directly
- **Comprehensive calendar info** - Gets name, ID, description, writability
- **Event counting** - Counts events in each calendar
- **Fallback database access** - Alternative SQLite method if AppleScript fails

#### Sample Output:
```
=== macOS Calendar Configuration Helper ===

Found 3 calendar(s):

1. Home
   ID: 12345678-1234-1234-1234-123456789ABC
   Description: Personal calendar
   Events: 67

2. Work
   ID: 87654321-4321-4321-4321-CBA987654321
   Events: 134

3. Holidays
   ID: ABCDEFGH-ABCD-ABCD-ABCD-ABCDEFGHIJKL
   Events: 52

=== Configuration Snippet ===
"calendar_sources": [
    {
        "type": "outlook",
        "name": "Home",
        "calendar_name": "Home",
        "calendar_id": "12345678-1234-1234-1234-123456789ABC"
    },
    ...
]
```

### 🤖 Smart Outlook Mac Configuration

**Purpose**: Intelligently analyzes Outlook for Mac calendars and automatically generates optimized configurations for work environments.

#### Usage:
```bash
# On macOS with Outlook for Mac
cd /opt/calendar-agent/
python check_outlook_calendars.py
```

#### Advanced Intelligence:
- **Work calendar detection** - Filters out personal/system calendars
- **Email domain filtering** - Prioritizes corporate email domains
- **Event count analysis** - Filters calendars based on activity levels
- **Smart grouping** - Groups calendars by account for better organization
- **Automatic configuration generation** - Creates ready-to-use config files

#### Work Domain Configuration:
```python
# Configure your work domains in the script
work_domains = [
    'company.com', 
    'corporation.net', 
    'enterprise.org',
    'yourdomain.com'
]
```

#### Smart Filtering Logic:
```python
def is_work_calendar(cal_name, event_count, email=None):
    # Skip system calendars
    system_terms = ['holiday', 'birthday', 'holidays']
    if any(term in cal_name.lower() for term in system_terms):
        return False
    
    # Prefer work email domains
    if email and any(domain in email.lower() for domain in work_domains):
        return True
    
    # Filter by activity level
    return event_count >= min_events and event_count <= max_events
```

#### Sample Output:
```
=== Smart Outlook Mac Calendar Analysis ===

Analyzing calendar data...
Found 8 calendar folders with events
  - ID: 1, Events: 234, Email: john.doe@company.com
  - ID: 2, Events: 12, Email: john@gmail.com  
  - ID: 3, Events: 456, Email: team@company.com

Filtering for work calendars...
  - Skipping system calendar: Holidays
  - Skipping non-work email: john@gmail.com

✅ Configuration saved to outlook_config.json
Selected 2 calendars to sync:
  - Work Calendar (john.doe@company.com) (ID: 1)
  - Team Calendar (team@company.com) (ID: 3)
```

### 📁 Generated Files and Usage

#### Configuration Files Generated:
```bash
# Agent configuration (ready to use)
outlook_config.json              # Main agent configuration

# Reference files (for troubleshooting)
outlook_calendars_20240115_143022.json     # Windows Outlook details
outlook_mac_calendars_20240115_143022.json # Mac Outlook details  
macos_calendars_20240115_143022.json       # macOS Calendar details
```

#### Using Generated Configurations:

1. **Copy the agent files**:
```bash
# Windows
copy remote_agent.py C:\CalendarAgent\
copy outlook_config.json C:\CalendarAgent\
copy run_agent.bat C:\CalendarAgent\

# macOS
cp remote_agent.py /opt/calendar-agent/
cp outlook_config.json /opt/calendar-agent/
```

2. **Customize if needed**:
```json
{
  "agent_id": "office-mac-1",
  "agent_name": "John's MacBook",
  "environment": "Corporate Network",
  "central_api_url": "http://192.168.1.100:8008",
  "sync_interval_minutes": 30,
  "enable_bidirectional_sync": true,
  "calendar_sources": [
    // Generated calendar configurations here
  ]
}
```

3. **Start the agent**:
```bash
# Windows
run_agent.bat

# macOS
python remote_agent.py --config outlook_config.json
```

### 🔧 Advanced Configuration Options

#### Multi-Platform Agent Setup:
```json
{
  "agent_id": "multi-platform-agent",
  "calendar_sources": [
    {
      "type": "outlook",
      "name": "Windows Outlook Calendar",
      "calendar_name": "Calendar"
    },
    {
      "type": "outlook_mac", 
      "name": "Mac Outlook Calendar",
      "calendar_id": "ABCD-1234",
      "folder_id": "5",
      "account_uid": "2"
    },
    {
      "type": "macos_calendar",
      "name": "macOS Work Calendar", 
      "calendar_id": "12345678-1234-1234-1234-123456789ABC"
    }
  ]
}
```

#### Selective Calendar Sync:
```json
{
  "calendar_sources": [
    {
      "type": "outlook_mac",
      "name": "Primary Work Calendar",
      "calendar_id": "work-cal-id",
      "allow_metadata_updates": true,
      "allow_event_updates": true,
      "sync_filters": {
        "event_types": ["meeting", "appointment"],
        "exclude_private": true,
        "date_range_days": 90
      }
    }
  ]
}
```

### 🚀 Quick Setup Workflows

#### New Windows Machine:
```bash
# 1. Download discovery tool
curl -O http://your-server/tools/list_outlook_calendars.py

# 2. Run discovery
python list_outlook_calendars.py

# 3. Use generated config
# Config is automatically saved to outlook_config.json

# 4. Deploy agent
copy-agent-files.bat
```

#### New Mac Machine:
```bash
# 1. Download discovery tools
curl -O http://your-server/tools/list_outlook_mac_calendars.py
curl -O http://your-server/tools/check_outlook_calendars.py

# 2. Run smart discovery
python check_outlook_calendars.py

# 3. Deploy agent with generated config
./deploy-mac-agent.sh
```

#### Bulk Deployment:
```bash
# Generate configs for multiple machines
for machine in office-pc-1 office-pc-2 office-mac-1; do
  ssh $machine "python discover-calendars.py --output $machine-config.json"
  scp $machine:$machine-config.json ./configs/
done

# Deploy to all machines
ansible-playbook deploy-calendar-agents.yml
```

## Advanced Bidirectional Features

### Real-time Update Processing

#### Update Types and Processing:

```python
# Calendar metadata updates
{
  "type": "calendar_metadata",
  "data": {
    "calendar_id": "cal-123",
    "provider": "outlook",
    "changes": {
      "name": "New Calendar Name",
      "color": "#FF5733",
      "description": "Updated description"
    }
  }
}

# Sync configuration updates  
{
  "type": "sync_config",
  "data": {
    "changes": {
      "sync_interval_minutes": 15,
      "enable_bidirectional_sync": true
    }
  }
}

# Event updates (create/update/delete)
{
  "type": "event_update", 
  "data": {
    "action": "update",
    "event": {
      "id": "event-123",
      "title": "Updated Meeting",
      "start_time": "2024-01-15T10:00:00Z",
      "end_time": "2024-01-15T11:00:00Z"
    }
  }
}

# Calendar creation/deletion
{
  "type": "calendar_create",
  "data": {
    "provider": "google",
    "calendar": {
      "name": "New Project Calendar",
      "color": "#4285F4"
    }
  }
}
```

#### Processing Flow in Remote Agents:

```python
# Enhanced remote_agent.py processing
async def process_pending_updates(self, updates):
    for update in updates:
        try:
            if update["type"] == "calendar_metadata":
                await self.apply_calendar_metadata_update(update["data"])
            elif update["type"] == "sync_config":
                await self.apply_sync_config_update(update["data"])
            elif update["type"] == "event_update":
                await self.apply_event_update(update["data"])
            
            # Confirm processing
            await self.mark_update_processed(update["id"])
            
        except Exception as e:
            logger.error(f"Failed to process update {update['id']}: {e}")
            # Update will be retried on next heartbeat
```

### Integration with Frontend Applications

#### Next.js/React Integration:

```typescript
// CalendarClient.ts - Enhanced with bidirectional operations
export class CalendarClient {
  constructor(private baseUrl: string) {}

  // Get calendars with real-time sync status
  async getCalendars(credentials: any): Promise<CalendarList> {
    const response = await fetch(`${this.baseUrl}/calendars`, {
      method: 'GET',
      headers: { 
        'Content-Type': 'application/json',
        'X-Credentials': JSON.stringify(credentials)
      }
    });
    return response.json();
  }

  // Update calendar metadata (triggers bidirectional sync)
  async updateCalendarMetadata(
    calendarId: string, 
    updates: MetadataUpdates,
    provider: string,
    credentials: any
  ): Promise<UpdateResult> {
    const response = await fetch(`${this.baseUrl}/calendars/${calendarId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates),
      params: new URLSearchParams({
        provider,
        credentials: JSON.stringify(credentials)
      })
    });
    return response.json();
  }

  // Push changes to specific agents
  async pushToAgents(
    changes: any, 
    targetAgents?: string[]
  ): Promise<PushResult> {
    const response = await fetch(`${this.baseUrl}/sync/push/calendar-metadata`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ changes, target_agents: targetAgents })
    });
    return response.json();
  }

  // Monitor sync status across agents
  async getAgentStatus(): Promise<AgentStatus[]> {
    const response = await fetch(`${this.baseUrl}/sync/agents/status`);
    return response.json();
  }
}
```

#### React Component Example:

```tsx
// CalendarSyncComponent.tsx - Enhanced with bidirectional controls
import React, { useState, useEffect } from 'react';
import { CalendarClient } from './CalendarClient';

export const CalendarSyncComponent: React.FC = () => {
  const [calendars, setCalendars] = useState([]);
  const [agentStatus, setAgentStatus] = useState([]);
  const [syncInProgress, setSyncInProgress] = useState(false);
  
  const client = new CalendarClient(process.env.NEXT_PUBLIC_CALENDAR_API_URL);

  // Real-time agent status monitoring
  useEffect(() => {
    const pollAgentStatus = async () => {
      try {
        const status = await client.getAgentStatus();
        setAgentStatus(status.agent_status);
      } catch (error) {
        console.error('Failed to get agent status:', error);
      }
    };

    const interval = setInterval(pollAgentStatus, 30000); // Poll every 30 seconds
    pollAgentStatus(); // Initial call
    
    return () => clearInterval(interval);
  }, []);

  // Handle calendar rename with bidirectional sync
  const handleCalendarRename = async (calendarId: string, newName: string) => {
    setSyncInProgress(true);
    try {
      const result = await client.updateCalendarMetadata(
        calendarId,
        { name: newName },
        'outlook', // or dynamic provider
        userCredentials
      );
      
      console.log('Calendar renamed, propagating to agents...', result);
      
      // Optional: Force immediate push to all agents
      await client.pushToAgents({
        calendar_id: calendarId,
        provider: 'outlook',
        changes: { name: newName }
      });
      
      // Refresh calendar list
      await loadCalendars();
      
    } catch (error) {
      console.error('Failed to rename calendar:', error);
    } finally {
      setSyncInProgress(false);
    }
  };

  // Agent status indicator
  const AgentStatusIndicator = ({ agent }: { agent: any }) => (
    <div className={`agent-status ${agent.status}`}>
      <span className="agent-name">{agent.name}</span>
      <span className={`status-dot ${agent.status === 'active' ? 'green' : 'red'}`}></span>
      <span className="last-checkin">
        Last seen: {new Date(agent.last_check_in).toLocaleString()}
      </span>
    </div>
  );

  return (
    <div className="calendar-sync-dashboard">
      <div className="sync-header">
        <h2>Bidirectional Calendar Sync</h2>
        {syncInProgress && <div className="sync-spinner">Syncing...</div>}
      </div>

      {/* Agent Status Panel */}
      <div className="agent-status-panel">
        <h3>Connected Agents</h3>
        {Object.entries(agentStatus).map(([agentId, agent]) => (
          <AgentStatusIndicator key={agentId} agent={agent} />
        ))}
      </div>

      {/* Calendar Management */}
      <div className="calendar-list">
        {calendars.map(calendar => (
          <div key={calendar.id} className="calendar-item">
            <input
              type="text"
              value={calendar.name}
              onChange={(e) => handleCalendarRename(calendar.id, e.target.value)}
              onBlur={(e) => {
                if (e.target.value !== calendar.name) {
                  handleCalendarRename(calendar.id, e.target.value);
                }
              }}
            />
            <span className="sync-status">
              {calendar.sync_status === 'synced' ? '✅' : '⏳'}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};
```

## Monitoring and Troubleshooting Bidirectional Sync

### Health Monitoring

#### Master Server Monitoring:

```bash
# Overall system health
curl http://master-server:8008/health

# Bidirectional sync status
curl http://master-server:8008/sync/agents/status

# Update queue status
curl http://master-server:8008/sync/queues/status

# Recent sync activity
curl http://master-server:8008/sync/activity/recent
```

#### Agent Health Checks:

```bash
# Check agent connectivity
curl http://master-server:8008/sync/agents/{agent-id}/status

# View pending updates for agent
curl http://master-server:8008/sync/agents/{agent-id}/pending-updates

# Agent processing history
curl http://master-server:8008/sync/agents/{agent-id}/history
```

### Common Issues and Solutions

#### **Issue**: Updates not reaching remote agents
**Symptoms**: Calendar changes in master don't appear in agent calendars
**Solution**:
```bash
# Check agent connectivity
curl http://master-server:8008/sync/agents/status

# Verify update queues
curl http://master-server:8008/sync/agents/{agent-id}/pending-updates

# Check agent logs
tail -f calendar_agent.log | grep "pending_updates"

# Manual update check
curl -X POST http://master-server:8008/sync/agents/{agent-id}/receive-updates \
  -H "Content-Type: application/json" \
  -d '{"type": "test", "data": {}}'
```

#### **Issue**: Conflict resolution not working
**Symptoms**: Different values in different calendars after simultaneous changes
**Solution**:
```bash
# Check conflict resolution strategy
grep CONFLICT_RESOLUTION .env

# View conflict history
curl http://master-server:8008/sync/conflicts/recent

# Manual conflict resolution
curl -X POST http://master-server:8008/sync/conflicts/{conflict-id}/resolve \
  -H "Content-Type: application/json" \
  -d '{"resolution": "source_wins"}'
```

#### **Issue**: Agent not processing updates
**Symptoms**: Updates queued but not applied locally
**Solution**:
```bash
# Check agent configuration
cat outlook_config.json | grep allow_metadata_updates

# Verify local calendar permissions
# For Outlook: Check if Outlook allows programmatic access
# For Google: Verify API credentials and scopes

# Test local calendar access
python -c "
from remote_agent import RemoteCalendarAgent
agent = RemoteCalendarAgent('outlook_config.json')
# Test calendar connection
"

# Check agent processing logs
grep "apply_calendar_metadata_update" calendar_agent.log
```

### Performance Optimization

#### Queue Management:

```bash
# Monitor Redis queue sizes
docker-compose exec redis redis-cli INFO memory

# View queue statistics
curl http://master-server:8008/sync/queues/stats

# Purge old processed updates
curl -X POST http://master-server:8008/sync/queues/cleanup

# Adjust queue retention
echo "UPDATE_QUEUE_RETENTION_DAYS=3" >> .env
docker-compose restart calendar-service
```

#### Agent Performance Tuning:

```json
{
  "sync_interval_minutes": 15,  // Reduce for faster updates
  "update_processing_timeout": 600,  // Increase for slow calendars  
  "max_retry_attempts": 5,  // Increase for unreliable networks
  "batch_size": 100,  // Adjust for large calendars
  "enable_compression": true  // Reduce bandwidth usage
}
```

## Security Considerations for Bidirectional Sync

### Authentication and Authorization

#### API Security:
```bash
# Enable API authentication
AUTH_ENABLED=true
JWT_SECRET=your-super-secret-jwt-key
API_KEY_REQUIRED=true

# Rate limiting
RATE_LIMIT_REQUESTS_PER_MINUTE=100
RATE_LIMIT_AGENTS_PER_MINUTE=1000
```

#### Agent Authentication:
```json
{
  "agent_id": "office-pc-1",
  "agent_secret": "unique-agent-secret-key",
  "certificate_path": "/path/to/agent-cert.pem",
  "enable_tls": true
}
```

### Network Security

#### TLS Configuration:
```yaml
# docker-compose.yml
services:
  calendar-service:
    environment:
      - ENABLE_TLS=true
      - TLS_CERT_PATH=/certs/server.crt
      - TLS_KEY_PATH=/certs/server.key
    volumes:
      - ./certs:/certs:ro
```

#### Firewall Rules:
```bash
# Master server
sudo ufw allow from 192.168.1.0/24 to any port 8008  # Restrict to known networks
sudo ufw deny 8008  # Deny all other access

# Agent networks  
# Only allow outbound to master server
iptables -A OUTPUT -d 192.168.1.100 -p tcp --dport 8008 -j ACCEPT
iptables -A OUTPUT -p tcp --dport 8008 -j DROP
```

### Data Protection

#### Credential Encryption:
```json
{
  "calendar_sources": [
    {
      "type": "google",
      "credentials": {
        "encrypted": true,
        "data": "encrypted-credential-blob",
        "key_id": "encryption-key-identifier"
      }
    }
  ]
}
```

#### Audit Logging:
```bash
# Enable comprehensive audit logs
AUDIT_LOGGING=true
AUDIT_LOG_LEVEL=INFO
AUDIT_INCLUDE_PAYLOADS=false  # Set to true for debugging only

# Log locations
docker-compose logs calendar-service | grep AUDIT
tail -f /var/log/calendar-sync/audit.log
```

## Deployment Strategies

### High Availability Setup

#### Multi-Master Configuration:
```yaml
# docker-compose.ha.yml
version: '3.8'
services:
  calendar-service-1:
    image: calendar-sync:latest
    environment:
      - MASTER_ID=master-1
      - REDIS_HOST=redis-cluster
      - ENABLE_CLUSTERING=true
    ports:
      - "8008:8008"
  
  calendar-service-2:
    image: calendar-sync:latest  
    environment:
      - MASTER_ID=master-2
      - REDIS_HOST=redis-cluster
      - ENABLE_CLUSTERING=true
    ports:
      - "8009:8008"
  
  load-balancer:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
```

#### Redis Clustering:
```yaml
redis-cluster:
  image: redis:7-alpine
  command: redis-server --cluster-enabled yes --cluster-config-file nodes.conf
  ports:
    - "6379:6379"
  volumes:
    - redis-cluster-data:/data
```

### Kubernetes Deployment

#### Kubernetes Manifests:
```yaml
# k8s/calendar-sync-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: calendar-sync-master
spec:
  replicas: 3
  selector:
    matchLabels:
      app: calendar-sync-master
  template:
    metadata:
      labels:
        app: calendar-sync-master
    spec:
      containers:
      - name: calendar-sync
        image: calendar-sync:latest
        ports:
        - containerPort: 8008
        env:
        - name: REDIS_HOST
          value: "redis-service"
        - name: ENABLE_BIDIRECTIONAL_SYNC
          value: "true"
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: calendar-sync-service
spec:
  selector:
    app: calendar-sync-master
  ports:
  - protocol: TCP
    port: 8008
    targetPort: 8008
  type: LoadBalancer
```

### CI/CD Pipeline

#### GitHub Actions Example:
```yaml
# .github/workflows/deploy.yml
name: Deploy Calendar Sync

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-asyncio
    
    - name: Run tests
      run: |
        pytest tests/ -v
        python -m pytest tests/test_bidirectional_sync.py
    
    - name: Test bidirectional sync
      run: |
        python tests/integration/test_agent_communication.py
  
  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Build Docker image
      run: |
        docker build -t calendar-sync:${{ github.sha }} .
        docker tag calendar-sync:${{ github.sha }} calendar-sync:latest
    
    - name: Deploy to production
      run: |
        # Deploy to your production environment
        docker-compose -f docker-compose.prod.yml up -d
```

## Contributing to Bidirectional Sync

### Development Setup

```bash
# Clone and setup development environment
git clone <repo-url>
cd calendar_microservice

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install development dependencies
pip install -r requirements.txt
pip install -r requirements.dev.txt

# Setup pre-commit hooks
pre-commit install

# Start development services
docker-compose -f docker-compose.dev.yml up -d

# Run tests
pytest tests/ -v
```

### Testing Bidirectional Sync

```python
# tests/test_bidirectional_sync.py
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from sync.controller import CalendarSyncController
from sync.remote_agent import RemoteCalendarAgent

@pytest.mark.asyncio
async def test_calendar_metadata_update_propagation():
    """Test that calendar metadata updates propagate to agents"""
    # Setup
    controller = CalendarSyncController(storage_mock)
    agent = RemoteCalendarAgent('test_config.json')
    
    # Mock agent registration
    await controller.add_sync_agent(agent_config)
    
    # Trigger metadata update
    result = await controller.push_calendar_metadata_changes({
        'calendar_id': 'test-cal-1',
        'provider': 'outlook',
        'changes': {'name': 'Updated Calendar Name'}
    })
    
    # Verify update was queued
    assert result['updates_queued'] == 1
    
    # Simulate agent heartbeat
    pending = await controller.get_pending_updates_for_agent('test-agent-1')
    assert len(pending['updates']) == 1
    assert pending['updates'][0]['type'] == 'calendar_metadata'

@pytest.mark.asyncio 
async def test_conflict_resolution():
    """Test conflict resolution for simultaneous updates"""
    # Setup simultaneous updates
    update1 = {'name': 'Calendar A', 'updated_at': '2024-01-01T10:00:00Z'}
    update2 = {'name': 'Calendar B', 'updated_at': '2024-01-01T10:01:00Z'}
    
    # Test latest_wins strategy
    resolved = controller._resolve_conflict(update1, update2, 'latest_wins')
    assert resolved['name'] == 'Calendar B'  # Later timestamp wins

@pytest.mark.asyncio
async def test_agent_update_processing():
    """Test agent processing of incoming updates"""
    agent = RemoteCalendarAgent('test_config.json')
    
    # Mock calendar update
    with patch.object(agent, 'update_outlook_calendar_metadata') as mock_update:
        await agent.apply_calendar_metadata_update({
            'calendar_id': 'test-cal',
            'provider': 'outlook', 
            'changes': {'name': 'New Name'}
        })
        
        mock_update.assert_called_once()
```

### Feature Requests and Bug Reports

When contributing to bidirectional sync features:

1. **Feature Requests**: Include use case, expected behavior, and impact assessment
2. **Bug Reports**: Provide reproduction steps, logs, and environment details  
3. **Pull Requests**: Include tests for bidirectional sync functionality
4. **Documentation**: Update both code comments and this README

### Code Style and Standards

```python
# Follow these patterns for bidirectional sync code

# Use descriptive names for bidirectional operations
async def push_calendar_metadata_changes(self, changes, target_agents=None):
    """Push calendar metadata changes to remote agents."""
    pass

# Include comprehensive error handling  
try:
    await self.apply_calendar_metadata_update(update_data)
    await self.mark_update_processed(update_id)
except CalendarPermissionError:
    logger.error(f"Permission denied for calendar update: {update_id}")
    # Don't retry permission errors
except CalendarConnectionError:
    logger.warning(f"Connection failed for update: {update_id}")
    # Will retry on next heartbeat
except Exception as e:
    logger.error(f"Unexpected error processing update {update_id}: {e}")

# Use type hints for clarity
async def apply_calendar_metadata_update(
    self, 
    update_data: Dict[str, Any]
) -> bool:
    """Apply calendar metadata changes to local provider."""
    pass
```

## License

MIT License - see LICENSE file for details

---

## 🎯 Summary

This bidirectional calendar sync system provides:

✅ **Complete bidirectional synchronization** across all calendar providers  
✅ **Real-time change propagation** from any endpoint to all others  
✅ **Robust queue-based delivery** ensuring no updates are lost  
✅ **Intelligent conflict resolution** for simultaneous changes  
✅ **Comprehensive monitoring and troubleshooting** tools  
✅ **Enterprise-ready security and deployment** options  
✅ **Extensive documentation and examples** for quick implementation  

Whether you're syncing calendars across multiple offices, integrating with various calendar providers, or building a unified calendar interface, this system provides the reliability and flexibility needed for production environments.
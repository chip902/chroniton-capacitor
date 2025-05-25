# Simple Outlook Calendar Sync

This tool syncs your Outlook calendars from isolated networks to a central calendar. No OAuth or complicated setup required - it just works with your existing Windows login.

## Quick Start

1. **On your Windows machine with Outlook**:
   - Download and install Python from [python.org](https://www.python.org/downloads/) (make sure to check "Add to PATH")
   - Copy these 3 files to a folder:
     - `remote_agent.py` (the sync engine)
     - `outlook_config.json` (config file)
     - `run_agent.bat` (launcher)

2. **Edit the config file**:
   Open `outlook_config.json` in Notepad and change:
   ```
   "central_api_url": "http://your-central-service:8000"
   ```
   to the actual address of your central calendar server

3. **Run the agent**:
   - Double-click `run_agent.bat`
   - Click "Allow" if Outlook asks for permission
   - The agent will start syncing your calendars automatically

That's it! Your Outlook calendar events will now be sent to your central calendar server.

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

## Environment File

No environment file is needed for the remote agent. All configuration is in the `outlook_config.json` file.

The central server uses a `.env` file for configuration, which should include:

```
# Server settings
DEBUG=false
CORS_ORIGINS=http://localhost:3000,https://your-nextjs-app.com

# Redis for caching (if using)
REDIS_HOST=localhost
REDIS_PORT=6379

# Destination calendar (if using Google or Microsoft)
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/auth/google/callback

# Or for Microsoft
MS_CLIENT_ID=your-client-id
MS_CLIENT_SECRET=your-client-secret
MS_REDIRECT_URI=http://localhost:8000/api/auth/microsoft/callback
MS_TENANT_ID=your-tenant-id

# Sync settings
SYNC_INTERVAL_MINUTES=60
```
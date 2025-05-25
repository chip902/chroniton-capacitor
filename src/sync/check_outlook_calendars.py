import os
import sqlite3
import json
import subprocess
from datetime import datetime, timedelta


def is_work_calendar(cal_name, event_count, email=None):
    """Determine if a calendar is work-related"""
    # Skip system/holiday calendars
    system_terms = ['holiday', 'birthday', 'holidays']
    if any(term in cal_name.lower() for term in system_terms):
        print(f"  - Skipping system calendar: {cal_name}")
        return False

    # If we have an email, prefer work-related emails
    if email and ('@' in email):
        # Add your work email domain here
        work_domains = ['chip-hosting.com', 'amtrak.com', 'velir.com',
                        'quantsystemsinc.com', 'sonata-software.com', 'prj-3.com']
        if not any(domain in email.lower() for domain in work_domains):
            print(f"  - Skipping non-work email: {email}")
            return False

    return True


def get_calendar_names():
    """Get calendar names using AppleScript with better error handling"""
    script = '''
    tell application "Microsoft Outlook"
        set output to ""
        repeat with cal in calendars
            try
                set calName to name of cal
                set calId to id of cal as text
                set output to output & "{\\"name\\":\\"" & calName & "\\",\\"id\\":\\"" & calId & "\\"},"
            end try
        end repeat
        if length of output > 0 then
            set output to text 1 thru -2 of output -- remove trailing comma
        end if
        return "[" & output & "]"
    end tell
    '''

    try:
        result = subprocess.run(['osascript', '-e', script],
                                capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
    except Exception as e:
        print(f"Error getting calendar names: {e}")

    return []


def get_calendar_details(db_path, min_events=1, max_events=100000):
    """Get calendar details from the database with better filtering"""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    cursor = conn.cursor()

    # First, check what columns exist in CalendarEvents
    cursor.execute("PRAGMA table_info(CalendarEvents)")
    columns = [col[1] for col in cursor.fetchall()]
    print(f"Available columns in CalendarEvents: {columns}")

    # Build the query based on available columns
    select_columns = [
        "Record_FolderID",
        "Record_AccountUID",
        "COUNT(*) as event_count",
        "GROUP_CONCAT(DISTINCT substr(Record_ExchangeOrEasId, 1, 500)) as sample_ids",
        "MAX(Calendar_StartDateUTC) as last_event_date"
    ]

    # Only include Calendar_Organizer if it exists
    if 'Calendar_Organizer' in columns:
        select_columns.insert(
            4, "GROUP_CONCAT(DISTINCT substr(Calendar_Organizer, 1, 500)) as organizers")

    query = f"""
        SELECT 
            {', '.join(select_columns)}
        FROM CalendarEvents
        WHERE Record_FolderID IS NOT NULL
        GROUP BY Record_FolderID, Record_AccountUID
        HAVING event_count >= ?
        ORDER BY event_count DESC
    """

    print(f"Executing query: {query}")
    cursor.execute(query, (min_events,))

    calendars = []
    for row in cursor.fetchall():
        try:
            # Unpack the row based on available columns
            if 'Calendar_Organizer' in columns:
                folder_id, account_uid, event_count, sample_ids, organizers, last_event = row
            else:
                folder_id, account_uid, event_count, sample_ids, last_event = row
                organizers = None

            print(f"\nProcessing calendar {folder_id}:")
            print(f"  Events: {event_count}, Last event: {last_event}")

            # Skip calendars with too many events (likely system)
            if event_count > max_events:
                print(f"  - Skipping: too many events ({event_count})")
                continue

            # Try to extract email from multiple sources
            email = None
            sources = []

            # 1. Check sample_ids
            if sample_ids:
                sources.append(sample_ids)

            # 2. Check organizers if available
            if organizers:
                sources.append(organizers)

            # Try to find email in all sources
            for source in sources:
                if not source:
                    continue
                # Look for email patterns
                import re
                email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
                matches = re.findall(email_pattern, source)
                if matches:
                    email = matches[0].lower()
                    print(f"  Found email: {email}")
                    break

            calendars.append({
                'folder_id': str(folder_id),
                'account_uid': str(account_uid),
                'event_count': event_count,
                'email': email,
                'last_event': last_event
            })

        except Exception as e:
            print(f"Error processing row: {e}")
            continue

    conn.close()
    return calendars


def generate_config(calendars, calendar_names):
    """Generate a clean config file with work-related calendars"""
    if not calendars:
        print(
            "\nNo calendars found. Creating a default config with all available calendars.")
        # Fall back to a simpler config generation
        return {
            'agent_id': 'outlook-mac-agent',
            'agent_name': 'Outlook for Mac',
            'environment': 'Local',
            'central_api_url': 'http://localhost:8008',
            'sync_interval_minutes': 30,
            'calendar_sources': [
                {
                    'type': 'outlook_mac',
                    'name': 'Primary Calendar',
                    'folder_id': '1',
                    'account_uid': '1'
                }
            ]
        }

    # Group by account UID
    accounts = {}
    for cal in calendars:
        if cal['account_uid'] not in accounts:
            accounts[cal['account_uid']] = []
        accounts[cal['account_uid']].append(cal)

    selected_calendars = []
    for account_id, cals in accounts.items():
        # Sort by most recent and most events
        cals.sort(key=lambda x: (x.get('last_event', 0),
                  x['event_count']), reverse=True)

        # Take up to 3 calendars per account (most recent/most events first)
        for cal in cals[:3]:  # Take up to 3 calendars per account
            # Get calendar name
            cal_name = f"Calendar {cal['folder_id']}"
            if calendar_names:
                for cal_info in calendar_names:
                    if str(cal_info.get('id')) == str(cal['folder_id']):
                        cal_name = cal_info.get('name', cal_name)
                        break

            # Add email to name if available
            if cal.get('email'):
                cal_name = f"{cal_name} ({cal['email']})"

            # Only add if it's a work calendar or we don't have any calendars yet
            if not selected_calendars or is_work_calendar(cal_name, cal['event_count'], cal.get('email')):
                selected_calendars.append({
                    'type': 'outlook_mac',
                    'name': cal_name,
                    'folder_id': cal['folder_id'],
                    'account_uid': cal['account_uid']
                })

    # If we still don't have any calendars, include the top 3
    if not selected_calendars:
        print("No work calendars found, including top 3 calendars")
        for cal in calendars[:3]:
            cal_name = f"Calendar {cal['folder_id']}"
            if calendar_names:
                for cal_info in calendar_names:
                    if str(cal_info.get('id')) == str(cal['folder_id']):
                        cal_name = cal_info.get('name', cal_name)
                        break
            selected_calendars.append({
                'type': 'outlook_mac',
                'name': cal_name,
                'folder_id': cal['folder_id'],
                'account_uid': cal['account_uid']
            })

    return {
        'agent_id': 'outlook-mac-agent',
        'agent_name': 'Outlook for Mac',
        'environment': 'Local',
        'central_api_url': 'http://localhost:8008',
        'sync_interval_minutes': 30,
        'calendar_sources': selected_calendars
    }


def main():
    outlook_dir = os.path.expanduser(
        "~/Library/Group Containers/UBF8T346G9.Office/Outlook/Outlook 15 Profiles/Main Profile/Data"
    )
    db_path = os.path.join(outlook_dir, "Outlook.sqlite")

    print(f"Looking for database at: {db_path}")
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        print("Available files in directory:")
        try:
            for f in os.listdir(outlook_dir):
                print(f"  - {f}")
        except Exception as e:
            print(f"Could not list directory: {e}")
        return

    print("Getting calendar names from Outlook...")
    calendar_names = get_calendar_names()
    print(f"Found {len(calendar_names or [])} calendar names from Outlook")

    print("\nAnalyzing calendar data...")
    calendars = get_calendar_details(
        db_path, min_events=1)  # Reduced min_events to 1

    print(f"\nFound {len(calendars)} calendar folders with events")
    for cal in sorted(calendars, key=lambda x: x['event_count'], reverse=True):
        print(
            f"  - ID: {cal['folder_id']}, Events: {cal['event_count']}, Email: {cal.get('email', 'N/A')}")

    config = generate_config(calendars, calendar_names)

    # Save config
    config_path = "outlook_config.json"
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)

    print(f"\n✅ Configuration saved to {os.path.abspath(config_path)}")
    if config['calendar_sources']:
        print(f"Selected {len(config['calendar_sources'])} calendars to sync:")
        for cal in config['calendar_sources']:
            print(f"  - {cal['name']} (ID: {cal['folder_id']})")
    else:
        print("No calendars selected. Using default configuration.")


if __name__ == "__main__":
    main()

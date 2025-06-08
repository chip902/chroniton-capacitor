#!/usr/bin/env python3
"""
Outlook for Mac Calendar Lister

This script lists all available calendars from Outlook for Mac
and generates a configuration for the calendar sync agent.
"""

import os
import sqlite3
import json
import argparse
from datetime import datetime


def get_outlook_mac_database_path():
    """Get the path to the Outlook for Mac database"""
    # Use the exact path where we found the database
    db_path = os.path.expanduser(
        "~/Library/Group Containers/UBF8T346G9.Office/Outlook/Outlook 15 Profiles/Main Profile/Data/Outlook.sqlite"
    )

    print(f"Checking: {db_path}")

    if os.path.exists(db_path):
        print("  Found Outlook database")
        # Verify we can access the database
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            required_tables = {'Folders', 'AccountsMail', 'AccountsExchange'}
            table_names = {table[0] for table in tables}
            conn.close()

            if required_tables.issubset(table_names):
                print(f"  Found all required tables in {db_path}")
                return db_path
            else:
                print(
                    f"  Warning: Missing some required tables. Found: {tables}")
                return None

        except sqlite3.Error as e:
            print(f"  Error accessing database: {e}")
            return None


def get_outlook_mac_calendars():
    """Get all available calendars from Outlook for Mac"""
    db_path = get_outlook_mac_database_path()
    if not db_path:
        print("\nCould not find Outlook database. Make sure Outlook is installed and has been run at least once.")
        return []

    print(f"\nFound Outlook database at: {db_path}")

    try:
        # Connect to the database
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        cursor = conn.cursor()

        print("\nFetching calendar folders...")
        # Get all calendar folders
        cursor.execute("""
            SELECT Record_RecordID as id, 
                   Folder_Name as name,
                   Record_AccountUID as account_uid,
                   Folder_FolderType as folder_type
            FROM Folders
            WHERE Folder_FolderType = 'IPF.Appointment' OR 
                  Folder_FolderType = 'IPF.Calendar' OR
                  Folder_Name LIKE '%Calendar%'
            ORDER BY Folder_Name
        """)

        calendars = []
        for folder in cursor.fetchall():
            folder_id = folder['id']
            folder_name = folder['name']
            account_uid = folder['account_uid']

            # Get account info
            cursor.execute("""
                SELECT Account_EmailAddress as email, 
                       Account_Name as name
                FROM AccountsMail
                WHERE Record_RecordID = ?
            """, (account_uid,))

            account = cursor.fetchone()
            if account:
                account_email = account['email'] or ""
                account_name = account['name'] or "Unknown"
            else:
                # Try to get from Exchange accounts
                cursor.execute("""
                    SELECT Account_EmailAddress as email, 
                           Account_Name as name
                    FROM AccountsExchange
                    WHERE Record_RecordID = ?
                """, (account_uid,))
                exchange_account = cursor.fetchone()
                if exchange_account:
                    account_email = exchange_account['email'] or ""
                    account_name = exchange_account['name'] or "Unknown"
                else:
                    account_email = ""
                    account_name = "Unknown"

            # Count events in this calendar
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM CalendarEvents
                WHERE Record_FolderID = ?
            """, (folder_id,))
            event_count = cursor.fetchone()['count']

            # Get calendar color if available
            cursor.execute("""
                SELECT Category_BackgroundColor
                FROM Categories
                WHERE Record_FolderID = ?
                LIMIT 1
            """, (folder_id,))

            color_row = cursor.fetchone()
            color = "#1a73e8"  # Default blue color
            if color_row and color_row[0]:
                try:
                    # Convert from BGR to RGB hex
                    bgr = int(color_row[0])
                    r = bgr & 0xff
                    g = (bgr >> 8) & 0xff
                    b = (bgr >> 16) & 0xff
                    color = f"#{r:02x}{g:02x}{b:02x}"
                except (ValueError, TypeError):
                    pass

            calendar_data = {
                'id': str(folder_id),
                'name': folder_name,
                'display_name': folder_name,
                'account_name': account_name,
                'account_email': account_email,
                'account_type': 'Email' if account_email else 'Local Calendar',
                'event_count': event_count,
                'color': color,
                'enabled': True,
                'path': "",
                'last_sync': ""
            }

            print(
                f"  Found calendar: {calendar_data['name']} ({event_count} events)")
            calendars.append(calendar_data)

        conn.close()
        return calendars

    except sqlite3.Error as e:
        print(f"Error accessing Outlook database: {e}")
        import traceback
        traceback.print_exc()
        return []


def main():
    """Main function to list calendars and generate config"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Outlook for Mac Calendar Configuration Generator")
    parser.add_argument("--output", "-o", default="outlook_config.json", 
                      help="Output file name for the configuration (default: outlook_config.json)")
    parser.add_argument("--backup", "-b", action="store_true",
                      help="Create a timestamped backup file in addition to the main output")
    
    args = parser.parse_args()
    
    print("\n=== Outlook for Mac Calendar Configuration Helper ===\n")
    print("Searching for Outlook calendars...\n")

    calendars = get_outlook_mac_calendars()

    if not calendars:
        print("No calendars found. Make sure Outlook for Mac is installed and configured.")
        return

    print(f"\nFound {len(calendars)} calendar(s):\n")

    # Display calendar information
    for idx, cal in enumerate(calendars, 1):
        print(f"{idx}. {cal['name']}")
        print(f"   Account: {cal['account_name']}")
        print(f"   Email: {cal['account_email'] or 'N/A'}")
        print(f"   Type: {cal['account_type']}")
        print(f"   Events: {cal['event_count']}")
        print(f"   Color: {cal['color']}")
    
    # Enhanced calendar data for better compatibility with agent
    calendar_sources = []
    for cal in calendars:
        config = {
            'type': 'outlook',
            'name': cal['name'],
            'display_name': cal['display_name'],
            'id': cal['id'],
            'account_name': cal['account_name'],
            'account_email': cal['account_email'],
            'account_type': cal['account_type'],
            'event_count': cal['event_count'],
            'color': cal['color'],
            'enabled': cal['enabled'],
            'path': cal['path'] or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'outlook_data'),
            'source_id': f"outlook-{cal['id']}",
            'provider': 'outlook',
            'sync_mode': 'read_only',  # Default to read-only
            'last_sync': ""
        }
        calendar_sources.append(config)
    
    # Generate config snippet for display
    print("\n=== Configuration Snippet ===\n")
    print("Use the following in your agent_config.json file (calendar_sources section):")
    print('"calendar_sources": [')

    for config in calendar_sources:
        print(f'    {json.dumps(config, indent=4, ensure_ascii=False)},')

    print(']')
    print("\n=== End of Configuration ===\n")

    # Save to the specified output file
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(calendar_sources, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\nConfiguration saved to: {os.path.abspath(args.output)}")
    
    # Create timestamped backup if requested
    if args.backup:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"outlook_mac_calendars_{timestamp}.json"
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(calendar_sources, f, indent=2, ensure_ascii=False, default=str)
        print(f"Backup saved to: {os.path.abspath(backup_file)}")


if __name__ == "__main__":
    main()

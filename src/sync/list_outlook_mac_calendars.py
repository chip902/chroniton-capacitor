"""
Outlook for Mac Calendar Lister

This script lists all available calendars from Outlook for Mac
to help with calendar sync configuration.
"""

import subprocess
import json
from datetime import datetime
import os
import sqlite3
from pprint import pprint

def find_sqlite_files(directory, max_depth=3, current_depth=0):
    """Recursively find all SQLite files in a directory"""
    if current_depth > max_depth:
        return []
        
    sqlite_files = []
    try:
        with os.scandir(directory) as it:
            for entry in it:
                try:
                    if entry.is_file() and entry.name.endswith(('.sqlite', '.sqlitedb', '.db')):
                        sqlite_files.append(entry.path)
                    elif entry.is_dir() and not entry.is_symlink():
                        sqlite_files.extend(find_sqlite_files(entry.path, max_depth, current_depth + 1))
                except (PermissionError, OSError):
                    continue
    except (PermissionError, OSError):
        pass
        
    return sqlite_files

def get_outlook_mac_database_path():
    """Find the path to the Outlook for Mac database"""
    # Common paths where Outlook for Mac stores its database
    possible_paths = [
        os.path.expanduser("~/Library/Group Containers/UBF8T346G9.Office/Outlook/Outlook 15 Profiles/Main Profile/Data/"),
        os.path.expanduser("~/Library/Group Containers/UBF8T346G9.Office/Outlook/"),
        os.path.expanduser("~/Library/Group Containers/UBF8T346G9.Office/"),
        os.path.expanduser("~/Library/Containers/com.microsoft.Outlook/Data/Library/Application Support/Microsoft/Outlook/"),
        os.path.expanduser("~/Library/Application Support/Microsoft/Office/Outlook/"),
        os.path.expanduser("~/Library/Containers/com.microsoft.Outlook/Data/Library/Caches/"),
    ]
    
    print("\nSearching for Outlook database in common locations...")
    
    # Check common paths first
    for path in possible_paths:
        if os.path.exists(path):
            print(f"\nChecking: {path}")
            for root, dirs, files in os.walk(path, topdown=True):
                # Skip some uninteresting directories
                dirs[:] = [d for d in dirs if not d.startswith('.') and 'Cache' not in d]
                
                for file in files:
                    if file.endswith(('.sqlite', '.sqlitedb', '.db')) and 'calendar' in file.lower():
                        db_path = os.path.join(root, file)
                        print(f"  Found potential database: {db_path}")
                        # Try to open the database to verify
                        try:
                            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
                            cursor = conn.cursor()
                            # Check if it has the expected tables
                            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ZFOLDER';")
                            if cursor.fetchone():
                                conn.close()
                                return db_path
                            conn.close()
                        except sqlite3.Error:
                            continue
    
    # If we get here, do a broader search
    print("\nPerforming broader search for Outlook database files...")
    search_paths = [
        os.path.expanduser("~/Library/Group Containers/"),
        os.path.expanduser("~/Library/Containers/"),
        os.path.expanduser("~/Library/Application Support/")
    ]
    
    for path in search_paths:
        if os.path.exists(path):
            print(f"\nSearching in: {path}")
            sqlite_files = find_sqlite_files(path, max_depth=5)
            for db_path in sqlite_files:
                if 'outlook' in db_path.lower() or 'office' in db_path.lower() or 'microsoft' in db_path.lower():
                    print(f"  Found potential database: {db_path}")
                    try:
                        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
                        cursor = conn.cursor()
                        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ZFOLDER';")
                        if cursor.fetchone():
                            conn.close()
                            return db_path
                        conn.close()
                    except sqlite3.Error:
                        continue
    
    print("\nCould not find Outlook database. Here are some troubleshooting steps:")
    print("1. Make sure Outlook for Mac is installed and has been run at least once")
    print("2. Check if you have any Microsoft 365 or Exchange accounts added in Outlook")
    print("3. The database might be in a different location if you're using an older version of Outlook")
    print("4. Try running 'mdfind -name '*.sqlite' | grep -i outlook' in Terminal to search for database files")
    
    return None

def get_outlook_mac_calendars():
    """Get all available calendars from Outlook for Mac"""
    try:
        # First try to find the database
        db_path = get_outlook_mac_database_path()
        if not db_path:
            print("Could not find Outlook for Mac database. Is Outlook installed?")
            return []
            
        print(f"Found Outlook database at: {db_path}")
        
        # Connect to the database
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cursor = conn.cursor()
        
        # Get calendar folders
        cursor.execute("""
            SELECT Z_PK, ZNAME, ZIDENTIFIER, ZCOLOR, ZISENABLED, ZACCOUNT
            FROM ZFOLDER
            WHERE ZFOLDERTYPE = 8  -- 8 is the folder type for calendars
            ORDER BY ZNAME
        """)
        
        calendars = []
        for row in cursor.fetchall():
            cal_id, name, identifier, color, is_enabled, account_id = row
            
            # Get account information
            cursor.execute("""
                SELECT ZACCOUNTNAME, ZACCOUNTTYPE
                FROM ZACCOUNT
                WHERE Z_PK = ?
            """, (account_id,))
            
            account_row = cursor.fetchone()
            account_name = account_row[0] if account_row else "Unknown Account"
            account_type = account_row[1] if account_row and len(account_row) > 1 else "Unknown"
            
            # Get event count
            cursor.execute("""
                SELECT COUNT(*)
                FROM ZCALENDARITEM
                WHERE ZFOLDER = ?
            """, (cal_id,))
            
            event_count = cursor.fetchone()[0]
            
            calendar = {
                'name': name,
                'id': identifier,
                'account_name': account_name,
                'account_type': account_type,
                'event_count': event_count,
                'color': f"#{color:06x}" if color else None,
                'enabled': bool(is_enabled)
            }
            calendars.append(calendar)
        
        conn.close()
        return calendars
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return []
    except Exception as e:
        print(f"Error getting Outlook calendars: {e}")
        return []

def main():
    """Main function to list calendars and generate config"""
    print("\n=== Outlook for Mac Calendar Configuration Helper ===\n")
    print("Searching for calendars in Outlook for Mac...\n")
    
    # Make sure Outlook is running
    try:
        subprocess.run(['osascript', '-e', 'tell application "Microsoft Outlook" to get name'], 
                      capture_output=True, check=True)
    except subprocess.CalledProcessError:
        print("Microsoft Outlook is not running. Starting Outlook...")
        try:
            subprocess.run(['open', '-a', 'Microsoft Outlook'])
            print("Please wait while Outlook starts, then run this script again.")
            return
        except Exception as e:
            print(f"Failed to start Outlook: {e}")
            return
    
    calendars = get_outlook_mac_calendars()
    
    if not calendars:
        print("No calendars found. Make sure you have at least one calendar in Outlook.")
        return
    
    print(f"Found {len(calendars)} calendar(s):\n")
    
    # Display calendar information
    for idx, cal in enumerate(calendars, 1):
        print(f"{idx}. {cal['name']}")
        print(f"   ID: {cal['id']}")
        print(f"   Account: {cal['account_name']} ({cal['account_type']})")
        print(f"   Events: {cal['event_count']}")
        if cal['color']:
            print(f"   Color: {cal['color']}")
        print()
    
    # Generate config snippet
    print("\n=== Configuration Snippet ===\n")
    print("Use the following in your outlook_config.json file:")
    print('"calendar_sources": [')
    
    for cal in calendars:
        config = {
            'type': 'outlook',
            'name': f"{cal['account_name']} - {cal['name']}",
            'calendar_name': cal['name'],
            'calendar_id': cal['id'],
            'account': cal['account_name']
        }
        print(f'    {json.dumps(config, indent=4)},')
    
    print(']')
    print("\n=== End of Configuration ===\n")
    
    # Save full details to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"outlook_mac_calendars_{timestamp}.json"
    with open(output_file, 'w') as f:
        json.dump(calendars, f, indent=2, default=str)
    
    print(f"\nFull calendar details saved to: {os.path.abspath(output_file)}")
    print("Use this file for reference when setting up your sync configuration.")
    
    print("\nNote: The calendar IDs are specific to your Outlook installation. "
          "You'll need to run this on each Mac where you set up the sync.")

if __name__ == "__main__":
    main()

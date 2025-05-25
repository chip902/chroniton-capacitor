"""
macOS Calendar Lister

This script lists all available calendars from the macOS Calendar app
to help with calendar sync configuration.
"""

import subprocess
import json
from datetime import datetime
import os
import plistlib
from pprint import pprint

def get_mac_calendars():
    """Get all available calendars from macOS Calendar app"""
    try:
        # Use AppleScript to get calendar information
        script = '''
        tell application "Calendar"
            set output to {}
            repeat with cal in calendars
                set calendarInfo to {name:name of cal, id:uid of cal, writable:writable of cal, description:description of cal}
                set end of output to calendarInfo
            end repeat
            return output
        end tell
        '''
        
        # Run the AppleScript
        result = subprocess.run(['osascript', '-e', script], 
                              capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"Error running AppleScript: {result.stderr}")
            return []
            
        # Parse the AppleScript output (it's in AppleScript record format)
        # Convert to proper JSON first
        raw_output = result.stdout.strip()
        
        # Clean up the output to make it valid JSON
        json_str = raw_output.replace('{name:', '{"name":') \
                            .replace(', id:', ', "id":') \
                            .replace(', writable:', ', "writable":') \
                            .replace(', description:', ', "description":') \
                            .replace('missing value', 'null')
        
        try:
            calendars = json.loads(f'[{json_str}]')
        except json.JSONDecodeError:
            # If the first method fails, try an alternative approach
            print("First method failed, trying alternative approach...")
            return get_mac_calendars_alternative()
        
        # Get event counts for each calendar
        for cal in calendars:
            cal['event_count'] = get_calendar_event_count(cal['id'])
            
        return calendars
        
    except Exception as e:
        print(f"Error getting calendars: {e}")
        return []

def get_mac_calendars_alternative():
    """Alternative method to get calendars using sqlite"""
    try:
        # Path to Calendar's database
        db_path = os.path.expanduser("~/Library/Calendars/Calendar Cache")
        
        # SQL query to get calendars
        query = """
        SELECT ZTITLE, ZIDENTIFIER, ZACCOUNTEXTERNALMODIFICATIONTAG, ZTITLE
        FROM ZCALENDAR
        WHERE ZTITLE IS NOT NULL
        """
        
        # Run the query
        result = subprocess.run(['sqlite3', db_path, query], 
                              capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"Error querying calendar database: {result.stderr}")
            return []
            
        calendars = []
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
                
            parts = line.split('|')
            if len(parts) >= 4:
                cal = {
                    'name': parts[0],
                    'id': parts[1],
                    'account': parts[2],
                    'title': parts[3],
                    'event_count': 0  # We can't easily get count without more complex queries
                }
                calendars.append(cal)
                
        return calendars
        
    except Exception as e:
        print(f"Error with alternative method: {e}")
        return []

def get_calendar_event_count(calendar_id):
    """Get the number of events in a calendar"""
    try:
        script = f'''
        tell application "Calendar"
            set cal to calendar id "{calendar_id}"
            return count of events of cal
        end tell
        '''
        
        result = subprocess.run(['osascript', '-e', script], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            return int(result.stdout.strip())
        return 0
    except:
        return 0

def main():
    """Main function to list calendars and generate config"""
    print("\n=== macOS Calendar Configuration Helper ===\n")
    print("Searching for calendars in macOS Calendar app...\n")
    
    calendars = get_mac_calendars()
    
    if not calendars:
        print("No calendars found. Make sure Calendar app is installed and you have at least one calendar configured.")
        return
    
    print(f"Found {len(calendars)} calendar(s):\n")
    
    # Display calendar information
    for idx, cal in enumerate(calendars, 1):
        print(f"{idx}. {cal.get('name', 'Unnamed Calendar')}")
        print(f"   ID: {cal.get('id', 'N/A')}")
        if 'description' in cal and cal['description']:
            print(f"   Description: {cal['description']}")
        if 'event_count' in cal:
            print(f"   Events: {cal['event_count']}")
        print()
    
    # Generate config snippet
    print("\n=== Configuration Snippet ===\n")
    print("Use the following in your outlook_config.json file (you may need to adjust the calendar names):")
    print('"calendar_sources": [')
    
    for cal in calendars:
        config = {
            'type': 'outlook',
            'name': cal.get('name', 'Unnamed Calendar'),
            'calendar_name': cal.get('name', 'Unnamed Calendar'),
            'calendar_id': cal.get('id', '')
        }
        print(f'    {json.dumps(config, indent=4)},')
    
    print(']')
    print("\n=== End of Configuration ===\n")
    
    # Save full details to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"macos_calendars_{timestamp}.json"
    with open(output_file, 'w') as f:
        json.dump(calendars, f, indent=2, default=str)
    
    print(f"\nFull calendar details saved to: {os.path.abspath(output_file)}")
    print("Use this file for reference when setting up your sync configuration.")
    
    print("\nNote: The calendar IDs are persistent but specific to your Mac. "
          "You may need to run this on each Mac where you set up the sync.")

if __name__ == "__main__":
    main()

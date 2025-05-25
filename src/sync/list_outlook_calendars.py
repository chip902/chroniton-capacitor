"""
Outlook Calendar Lister

This script lists all available Outlook calendars with their properties
to help with calendar sync configuration.
"""

import win32com.client
import json
from datetime import datetime
import os

def get_outlook_calendars():
    """Get all available Outlook calendars with their properties"""
    try:
        # Connect to Outlook
        outlook = win32com.client.Dispatch("Outlook.Application")
        namespace = outlook.GetNamespace("MAPI")
        
        # Get the default calendar folder
        calendar = namespace.GetDefaultFolder(9)  # 9 = olFolderCalendar
        
        # Get all calendar folders (including shared and secondary calendars)
        calendars = []
        
        def process_folder(folder, level=0):
            """Recursively process calendar folders"""
            try:
                # Get folder properties
                folder_info = {
                    'name': folder.Name,
                    'folder_path': folder.FolderPath,
                    'entry_id': folder.EntryID,
                    'store_id': getattr(folder, 'StoreID', None),
                    'default_item_type': folder.DefaultItemType,
                    'description': getattr(folder, 'Description', ''),
                    'items_count': folder.Items.Count,
                    'level': level
                }
                
                # Try to get more calendar-specific properties
                try:
                    appointments = folder.Items
                    if appointments.Count > 0:
                        appointment = appointments.GetFirst()
                        folder_info['sample_subject'] = getattr(appointment, 'Subject', 'No subject')
                        folder_info['sample_start'] = getattr(appointment, 'Start', 'No start time')
                except Exception as e:
                    folder_info['error'] = f"Error getting items: {str(e)}"
                
                calendars.append(folder_info)
                
                # Process subfolders
                for subfolder in folder.Folders:
                    process_folder(subfolder, level + 1)
                    
            except Exception as e:
                print(f"Error processing folder: {e}")
        
        # Start processing from the default calendar folder
        process_folder(calendar)
        
        # Also check other stores that might have calendars
        for store in namespace.Stores:
            try:
                root_folder = store.GetRootFolder()
                for folder in root_folder.Folders:
                    if folder.DefaultItemType == 1:  # 1 = olAppointmentItem
                        process_folder(folder)
            except Exception as e:
                print(f"Error processing store {store.DisplayName}: {e}")
        
        return calendars
        
    except Exception as e:
        print(f"Error connecting to Outlook: {e}")
        return []

def main():
    """Main function to list calendars and generate config"""
    print("\n=== Outlook Calendar Configuration Helper ===\n")
    print("Searching for Outlook calendars...\n")
    
    try:
        import win32com.client
    except ImportError:
        print("Error: pywin32 is required. Install it with: pip install pywin32")
        return
    
    calendars = get_outlook_calendars()
    
    if not calendars:
        print("No calendars found. Make sure Outlook is installed and configured.")
        return
    
    print(f"Found {len(calendars)} calendar(s):\n")
    
    # Display calendar information
    for idx, cal in enumerate(calendars, 1):
        print(f"{idx}. {cal['name']}")
        print(f"   Path: {cal['folder_path']}")
        print(f"   Entry ID: {cal['entry_id']}")
        print(f"   Store ID: {cal['store_id']}")
        print(f"   Description: {cal['description']}")
        print(f"   Items: {cal['items_count']} appointments")
        if 'sample_subject' in cal:
            print(f"   Sample: {cal['sample_subject']} at {cal['sample_start']}")
        print()
    
    # Generate config snippet
    print("\n=== Configuration Snippet ===\n")
    print("Use the following in your outlook_config.json file:")
    print('"calendar_sources": [')
    
    for cal in calendars:
        config = {
            'type': 'outlook',
            'name': cal['name'],
            'calendar_name': cal['name'],
            'calendar_id': cal['entry_id'],
            'store_id': cal['store_id']
        }
        print(f'    {json.dumps(config, indent=4)},')
    
    print(']')
    print("\n=== End of Configuration ===\n")
    
    # Save full details to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"outlook_calendars_{timestamp}.json"
    with open(output_file, 'w') as f:
        json.dump(calendars, f, indent=2, default=str)
    
    print(f"\nFull calendar details saved to: {os.path.abspath(output_file)}")
    print("Use this file for reference when setting up your sync configuration.")

if __name__ == "__main__":
    main()

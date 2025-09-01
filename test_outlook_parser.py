#!/usr/bin/env python3
"""
Test script for the OLK15EventParser
Run this to test Outlook for Mac event parsing
"""

import sys
import os
from pathlib import Path

# Add the src directory to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent / "src"))

from sync.olk15_parser import OLK15EventParser

def find_outlook_data_directory():
    """Try to find the Outlook data directory automatically"""
    possible_paths = [
        # Standard Outlook for Mac paths
        os.path.expanduser("~/Library/Group Containers/UBF8T346G9.Office/Outlook/Outlook 15 Profiles/Main Profile/Data"),
        os.path.expanduser("~/Library/Group Containers/UBF8T346G9.Office/Outlook/Outlook 16 Profiles/Main Profile/Data"),
        os.path.expanduser("~/Library/Containers/com.microsoft.Outlook/Data/Library/Application Support/Microsoft/Outlook"),
        
        # Alternative paths
        os.path.expanduser("~/Library/Application Support/Microsoft/Office/Outlook"),
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            events_dir = os.path.join(path, "Events")
            if os.path.exists(events_dir):
                return path
    
    return None

def test_parser_with_directory(outlook_data_dir: str):
    """Test the parser with a specific directory"""
    print(f"🔍 TESTING OUTLOOK MAC PARSER")
    print(f"Directory: {outlook_data_dir}")
    print("=" * 70)
    
    if not os.path.exists(outlook_data_dir):
        print(f"❌ Directory not found: {outlook_data_dir}")
        return False
    
    parser = OLK15EventParser(outlook_data_dir)
    
    # Test account discovery
    print("\n📁 DISCOVERING ACCOUNTS...")
    accounts = parser.get_account_directories()
    
    if not accounts:
        print("❌ No accounts found")
        return False
    
    print(f"✅ Found {len(accounts)} account directories:")
    for dir_num, account_info in accounts.items():
        print(f"   📂 Directory {dir_num}:")
        print(f"      Email: {account_info.get('email', 'Unknown')}")
        print(f"      Events: {account_info.get('event_count', 0)}")
        print(f"      Path: {account_info['path']}")
        print()
    
    # Test event parsing for the account with most events
    if accounts:
        # Find the account with the most events
        best_account = max(accounts.items(), key=lambda x: x[1].get('event_count', 0))
        dir_num, account_info = best_account
        
        if account_info.get('event_count', 0) > 0:
            print(f"🎯 PARSING EVENTS FROM ACCOUNT: {account_info.get('email', 'Unknown')} (Directory {dir_num})")
            print("=" * 70)
            
            try:
                events = parser.get_events_for_account(account_info['path'], days_back=7, days_forward=30)
                print(f"✅ Successfully parsed {len(events)} events")
                
                # Show first few events
                for i, event in enumerate(events[:3]):
                    print(f"\n  📅 Event {i+1}: {event.get('title', 'No title')}")
                    print(f"     Start: {event.get('start_time', 'N/A')}")
                    print(f"     End: {event.get('end_time', 'N/A')}")
                    print(f"     All Day: {event.get('all_day', False)}")
                    print(f"     Organizer: {event.get('organizer', 'N/A')}")
                    print(f"     Participants: {len(event.get('participants', []))}")
                    
                    if event.get('location'):
                        print(f"     Location: {event.get('location')}")
                    
                    if event.get('description'):
                        desc = event.get('description', '')[:100]
                        print(f"     Description: {desc}{'...' if len(event.get('description', '')) > 100 else ''}")
                
                if len(events) > 3:
                    print(f"\n   ... and {len(events) - 3} more events")
                
                return True
                
            except Exception as e:
                print(f"❌ Error parsing events: {e}")
                import traceback
                traceback.print_exc()
                return False
        else:
            print("⚠️  No events found in any accounts")
            return False
    
    return True

def main():
    """Main test function"""
    print("🧪 OUTLOOK MAC PARSER TEST")
    print("=" * 60)
    
    # Try to find Outlook data directory automatically
    outlook_data_dir = find_outlook_data_directory()
    
    if outlook_data_dir:
        print(f"✅ Found Outlook data directory: {outlook_data_dir}")
        success = test_parser_with_directory(outlook_data_dir)
    else:
        print("❌ Could not find Outlook data directory automatically")
        print("\n🔍 SEARCHING FOR OUTLOOK DIRECTORIES...")
        
        # Search more broadly
        possible_roots = [
            os.path.expanduser("~/Library/Group Containers"),
            os.path.expanduser("~/Library/Containers"),
            os.path.expanduser("~/Library/Application Support"),
        ]
        
        found_paths = []
        for root in possible_roots:
            if os.path.exists(root):
                for item in os.listdir(root):
                    if 'outlook' in item.lower() or 'office' in item.lower():
                        full_path = os.path.join(root, item)
                        if os.path.isdir(full_path):
                            found_paths.append(full_path)
        
        if found_paths:
            print("Found potential Outlook-related directories:")
            for path in found_paths[:10]:  # Show first 10
                print(f"  📁 {path}")
            
            print("\n⚠️  Manual setup required:")
            print("1. Find your Outlook data directory")
            print("2. Look for a directory containing 'Events' subdirectory")
            print("3. Run: python test_outlook_parser.py /path/to/outlook/data")
        else:
            print("❌ No Outlook directories found")
            print("Make sure Outlook for Mac is installed and has been run at least once")
        
        success = False
    
    # Print summary
    print(f"\n📊 SUMMARY")
    print("=" * 50)
    if success:
        print("✅ Outlook Mac parser is working!")
        print("🎯 Next steps:")
        print("   1. The parser can extract events from your Outlook data")
        print("   2. You can now use this in the full calendar sync system")
        print("   3. Consider setting up OAuth for Google/Microsoft for full sync")
    else:
        print("❌ Outlook Mac parser test failed")
        print("🔧 Troubleshooting:")
        print("   1. Make sure Outlook for Mac is installed")
        print("   2. Make sure you have calendar events in Outlook")
        print("   3. Check if the Events directory exists in your Outlook data")
        print("   4. You may need to grant permission to access Outlook data")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # User provided a directory path
        outlook_data_dir = sys.argv[1]
        test_parser_with_directory(outlook_data_dir)
    else:
        main()
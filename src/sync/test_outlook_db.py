#!/usr/bin/env python3
"""
Test script to check access to Outlook database
"""
import os
import sqlite3
import json

def test_database_access(db_path):
    """Test if we can access the Outlook database"""
    print(f"\nTesting access to database: {db_path}")
    
    if not os.path.exists(db_path):
        print(f"Error: Database file does not exist at {db_path}")
        return False
    
    try:
        # Try to connect to the database in read-only mode
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cursor = conn.cursor()
        
        # List all tables in the database
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print("\nFound tables:")
        for table in tables:
            print(f"- {table[0]}")
            
            # For each table, show the first few rows
            try:
                cursor.execute(f"SELECT * FROM {table[0]} LIMIT 1;")
                columns = [description[0] for description in cursor.description]
                print(f"  Columns: {', '.join(columns)}")
            except Exception as e:
                print(f"  Could not read table: {e}")
        
        conn.close()
        return True
        
    except sqlite3.Error as e:
        print(f"Error accessing database: {e}")
        return False

def main():
    # Path to the Outlook database
    db_path = os.path.expanduser(
        "~/Library/Group Containers/UBF8T346G9.Office/Outlook/Outlook 15 Profiles/Main Profile/Data/Outlook.sqlite"
    )
    
    # Test database access
    success = test_database_access(db_path)
    
    if success:
        print("\nSuccessfully accessed the Outlook database!")
    else:
        print("\nFailed to access the Outlook database.")

if __name__ == "__main__":
    main()

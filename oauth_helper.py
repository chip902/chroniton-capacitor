#!/usr/bin/env python3
"""
OAuth Helper Script for Chroniton Capacitor

This script makes it easier to authenticate multiple Google and Microsoft accounts
without manually copying/pasting authorization codes.
"""

import requests
import webbrowser
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import sys
import json
import time

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Handle OAuth callback and extract authorization code"""
    
    def do_GET(self):
        # Parse the callback URL
        parsed_url = urllib.parse.urlparse(self.path)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        
        if 'code' in query_params:
            # Got authorization code!
            auth_code = query_params['code'][0]
            self.server.auth_code = auth_code
            
            # Send success response
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            success_html = """
            <html>
                <head><title>Authorization Successful</title></head>
                <body>
                    <h2>✅ Authorization Successful!</h2>
                    <p>You can close this window and return to the terminal.</p>
                    <script>
                        setTimeout(function() { window.close(); }, 3000);
                    </script>
                </body>
            </html>
            """
            self.wfile.write(success_html.encode())
            
        elif 'error' in query_params:
            # OAuth error
            error = query_params['error'][0]
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            error_html = f"""
            <html>
                <head><title>Authorization Error</title></head>
                <body>
                    <h2>❌ Authorization Failed</h2>
                    <p>Error: {error}</p>
                </body>
            </html>
            """
            self.wfile.write(error_html.encode())
            
    def log_message(self, format, *args):
        # Suppress request logging
        pass


class OAuthHelper:
    def __init__(self, api_base_url="http://ark:8008"):
        self.api_base_url = api_base_url
        self.callback_port = 8009
        
    def authenticate_google_account(self, account_name="Google Account"):
        """Complete Google OAuth flow for an account"""
        print(f"\n🔐 Authenticating {account_name}...")
        
        # Step 1: Get authorization URL
        print("1. Getting authorization URL...")
        try:
            response = requests.get(f"{self.api_base_url}/sync/config/google/auth-url")
            response.raise_for_status()
            auth_data = response.json()
            auth_url = auth_data['auth_url']
        except Exception as e:
            print(f"❌ Failed to get auth URL: {e}")
            return None
        
        # Step 2: Start callback server
        print("2. Starting OAuth callback server...")
        server = HTTPServer(('localhost', self.callback_port), OAuthCallbackHandler)
        server.auth_code = None
        
        # Start server in background
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        
        # Step 3: Open browser for user authorization
        print("3. Opening browser for authorization...")
        print(f"   If browser doesn't open, visit: {auth_url}")
        webbrowser.open(auth_url)
        
        # Step 4: Wait for callback
        print("4. Waiting for authorization (please complete OAuth in browser)...")
        timeout = 300  # 5 minutes
        start_time = time.time()
        
        while server.auth_code is None and (time.time() - start_time) < timeout:
            time.sleep(1)
        
        server.shutdown()
        
        if server.auth_code is None:
            print("❌ Authorization timed out or failed")
            return None
        
        # Step 5: Exchange code for tokens
        print("5. Exchanging authorization code for tokens...")
        try:
            response = requests.post(
                f"{self.api_base_url}/sync/config/google/exchange-code",
                json={"code": server.auth_code}
            )
            response.raise_for_status()
            token_data = response.json()
            
            print("✅ Authentication successful!")
            return token_data['credentials']
            
        except Exception as e:
            print(f"❌ Failed to exchange code: {e}")
            return None
    
    def list_google_calendars(self, credentials):
        """List available calendars for authenticated Google account"""
        print("\n📅 Fetching available calendars...")
        try:
            response = requests.post(
                f"{self.api_base_url}/sync/config/google/calendars",
                json=credentials
            )
            response.raise_for_status()
            calendar_data = response.json()
            
            print(f"Found {calendar_data['total_count']} calendars:")
            for cal in calendar_data['calendars']:
                print(f"  📅 {cal['summary']} (ID: {cal['id']})")
            
            return calendar_data['calendars']
            
        except Exception as e:
            print(f"❌ Failed to list calendars: {e}")
            return []
    
    def create_sync_source(self, account_name, credentials, selected_calendars):
        """Create a sync source for the authenticated account"""
        print(f"\n⚙️ Creating sync source for {account_name}...")
        
        source_data = {
            "id": f"google_{account_name.lower().replace(' ', '_')}",
            "name": f"{account_name} Calendars",
            "provider_type": "google",
            "calendars": [cal['id'] for cal in selected_calendars],
            "credentials": credentials,
            "sync_method": "api",
            "sync_direction": "bidirectional",
            "enabled": True
        }
        
        try:
            response = requests.post(
                f"{self.api_base_url}/sync/sources",
                json=source_data
            )
            response.raise_for_status()
            result = response.json()
            
            print("✅ Sync source created successfully!")
            return result
            
        except Exception as e:
            print(f"❌ Failed to create sync source: {e}")
            return None


def main():
    print("🚀 Chroniton Capacitor OAuth Helper")
    print("=" * 40)
    
    helper = OAuthHelper()
    
    # Test server connectivity
    try:
        response = requests.get(f"{helper.api_base_url}/sync/health")
        response.raise_for_status()
        print("✅ Connected to Chroniton Capacitor API")
    except Exception as e:
        print(f"❌ Cannot connect to API: {e}")
        sys.exit(1)
    
    while True:
        print("\nWhat would you like to do?")
        print("1. Authenticate Google Account")
        print("2. List existing sync sources")
        print("3. Exit")
        
        choice = input("\nEnter choice (1-3): ").strip()
        
        if choice == "1":
            account_name = input("Enter account name (e.g., 'Work Gmail', 'Personal Gmail'): ").strip()
            if not account_name:
                account_name = "Google Account"
            
            # Authenticate account
            credentials = helper.authenticate_google_account(account_name)
            if not credentials:
                continue
            
            # List calendars
            calendars = helper.list_google_calendars(credentials)
            if not calendars:
                continue
            
            # Let user select calendars
            print("\nSelect calendars to sync (enter numbers separated by commas, or 'all'):")
            for i, cal in enumerate(calendars):
                print(f"{i+1}. {cal['summary']}")
            
            selection = input("\nSelection: ").strip().lower()
            
            if selection == 'all':
                selected_calendars = calendars
            else:
                try:
                    indices = [int(x.strip()) - 1 for x in selection.split(',')]
                    selected_calendars = [calendars[i] for i in indices if 0 <= i < len(calendars)]
                except:
                    print("❌ Invalid selection")
                    continue
            
            if selected_calendars:
                helper.create_sync_source(account_name, credentials, selected_calendars)
            
        elif choice == "2":
            try:
                response = requests.get(f"{helper.api_base_url}/sync/sources")
                response.raise_for_status()
                sources = response.json()
                
                if sources:
                    print("\n📋 Existing Sync Sources:")
                    for source in sources:
                        print(f"  • {source['name']} ({source['provider_type']}) - {len(source['calendars'])} calendars")
                else:
                    print("\n📋 No sync sources configured yet")
                    
            except Exception as e:
                print(f"❌ Failed to list sources: {e}")
            
        elif choice == "3":
            print("\n👋 Goodbye!")
            break
        
        else:
            print("❌ Invalid choice")


if __name__ == "__main__":
    main()
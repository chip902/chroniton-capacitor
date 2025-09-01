#!/usr/bin/env python3
"""
Test script to verify OAuth setup and configuration
Run this after setting up your .env file with OAuth credentials
"""

import asyncio
import sys
from pathlib import Path

# Add the src directory to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent / "src"))

from utils.config import settings
from auth.google_auth import GoogleCalendarAuth
from auth.microsoft_auth import MicrosoftGraphAuth

def test_configuration():
    """Test that configuration is loaded correctly"""
    print("🔧 TESTING CONFIGURATION")
    print("=" * 50)
    
    print(f"Environment: {settings.ENVIRONMENT}")
    print(f"Debug: {settings.DEBUG}")
    print(f"API Port: {settings.API_PORT}")
    print(f"Base URL: {settings.base_url}")
    print()
    
    # Test CORS configuration
    print(f"CORS Origins: {settings.CORS_ORIGINS}")
    print()
    
    # Test Google OAuth configuration
    print("Google OAuth Configuration:")
    print(f"  Client ID configured: {'✅' if settings.google_oauth_configured else '❌'}")
    print(f"  Redirect URI: {settings.google_redirect_uri}")
    print(f"  Scopes: {settings.GOOGLE_SCOPES}")
    print()
    
    # Test Microsoft OAuth configuration
    print("Microsoft OAuth Configuration:")
    print(f"  Client ID configured: {'✅' if settings.microsoft_oauth_configured else '❌'}")
    print(f"  Redirect URI: {settings.microsoft_redirect_uri}")
    print(f"  Tenant ID: {settings.MS_TENANT_ID}")
    print(f"  Scopes: {settings.MS_SCOPES}")
    print()

def test_google_auth():
    """Test Google authentication setup"""
    print("🔍 TESTING GOOGLE AUTHENTICATION")
    print("=" * 50)
    
    google_auth = GoogleCalendarAuth()
    
    if google_auth.dummy_mode:
        print("❌ Google OAuth is in dummy mode")
        print("   Please configure GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in your .env file")
        return False
    else:
        print("✅ Google OAuth is configured")
        
        # Test auth URL generation
        try:
            auth_result = google_auth.create_auth_url()
            print(f"✅ Auth URL generated: {auth_result['auth_url'][:100]}...")
            return True
        except Exception as e:
            print(f"❌ Error generating auth URL: {e}")
            return False

def test_microsoft_auth():
    """Test Microsoft authentication setup"""
    print("🔍 TESTING MICROSOFT AUTHENTICATION")
    print("=" * 50)
    
    ms_auth = MicrosoftGraphAuth()
    
    if ms_auth.dummy_mode:
        print("❌ Microsoft OAuth is in dummy mode")
        print("   Please configure MS_CLIENT_ID and MS_CLIENT_SECRET in your .env file")
        return False
    else:
        print("✅ Microsoft OAuth is configured")
        
        # Test auth URL generation
        try:
            auth_result = ms_auth.create_auth_url()
            print(f"✅ Auth URL generated: {auth_result['auth_url'][:100]}...")
            return True
        except Exception as e:
            print(f"❌ Error generating auth URL: {e}")
            return False

async def test_calendar_services():
    """Test that calendar services can be initialized"""
    print("📅 TESTING CALENDAR SERVICES")
    print("=" * 50)
    
    # Test Google Calendar service
    try:
        from services.google_calendar import GoogleCalendarService
        google_service = GoogleCalendarService()
        print("✅ Google Calendar service initialized")
    except Exception as e:
        print(f"❌ Error initializing Google Calendar service: {e}")
    
    # Test Microsoft Calendar service
    try:
        from services.microsoft_calendar import MicrosoftCalendarService
        ms_service = MicrosoftCalendarService()
        print("✅ Microsoft Calendar service initialized")
    except Exception as e:
        print(f"❌ Error initializing Microsoft Calendar service: {e}")

def print_next_steps():
    """Print next steps for the user"""
    print("\n🚀 NEXT STEPS")
    print("=" * 50)
    
    if not settings.google_oauth_configured and not settings.microsoft_oauth_configured:
        print("1. Set up OAuth credentials following OAUTH_SETUP.md")
        print("2. Copy .env.example to .env and fill in your credentials")
        print("3. Run this test script again")
    elif not settings.google_oauth_configured:
        print("1. Set up Google OAuth credentials (optional)")
        print("2. Start the application: python -m src.main")
        print("3. Test OAuth flows at: http://localhost:8008/api/auth/test")
    elif not settings.microsoft_oauth_configured:
        print("1. Set up Microsoft OAuth credentials (optional)")
        print("2. Start the application: python -m src.main")
        print("3. Test OAuth flows at: http://localhost:8008/api/auth/test")
    else:
        print("1. Start the application: python -m src.main")
        print("2. Test OAuth flows at: http://localhost:8008/api/auth/test")
        print("3. Try authorizing with Google: http://localhost:8008/api/auth/google/authorize")
        print("4. Try authorizing with Microsoft: http://localhost:8008/api/auth/microsoft/authorize")
    
    print("\n📚 For detailed setup instructions, see OAUTH_SETUP.md")

def main():
    """Main test function"""
    print("🧪 CHRONITON CAPACITOR OAUTH SETUP TEST")
    print("=" * 60)
    print()
    
    # Test configuration
    test_configuration()
    
    # Test authentication setups
    google_ok = test_google_auth()
    print()
    microsoft_ok = test_microsoft_auth()
    print()
    
    # Test calendar services
    asyncio.run(test_calendar_services())
    print()
    
    # Summary
    print("📊 SUMMARY")
    print("=" * 50)
    providers_configured = 0
    if google_ok:
        providers_configured += 1
        print("✅ Google Calendar OAuth ready")
    else:
        print("❌ Google Calendar OAuth not configured")
    
    if microsoft_ok:
        providers_configured += 1
        print("✅ Microsoft Graph OAuth ready")
    else:
        print("❌ Microsoft Graph OAuth not configured")
    
    print(f"\n🎯 {providers_configured}/2 OAuth providers configured")
    
    if providers_configured > 0:
        print("✅ You can start testing calendar integration!")
    else:
        print("⚠️  No OAuth providers configured. Please set up credentials first.")
    
    # Show next steps
    print_next_steps()

if __name__ == "__main__":
    main()
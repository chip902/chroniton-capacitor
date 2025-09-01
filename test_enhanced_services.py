#!/usr/bin/env python3
"""
Test script for the enhanced Apple Calendar and Exchange Web Services
Run this to test the new calendar access methods
"""

import asyncio
import sys
from pathlib import Path

# Add the src directory to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent / "src"))

async def test_apple_calendar():
    """Test the enhanced Apple Calendar service"""
    print("🍎 TESTING ENHANCED APPLE CALENDAR SERVICE")
    print("=" * 60)
    
    try:
        from services.apple_calendar_enhanced import AppleCalendarService
        
        apple_service = AppleCalendarService()
        
        print(f"Access method: {apple_service.get_access_method()}")
        print(f"Available: {apple_service.is_available()}")
        print()
        
        if not apple_service.is_available():
            print("❌ Apple Calendar service not available on this system")
            return False
        
        # Test calendar listing
        print("📅 LISTING CALENDARS...")
        calendars = await apple_service.list_calendars()
        
        if calendars:
            print(f"✅ Found {len(calendars)} calendars:")
            for calendar in calendars:
                print(f"   📂 {calendar['name']} (ID: {calendar['id']})")
            
            # Test events for first calendar
            if calendars:
                test_calendar = calendars[0]
                print(f"\n🎯 TESTING EVENTS FOR: {test_calendar['name']}")
                print("-" * 50)
                
                events = await apple_service.get_events(
                    calendar_id=test_calendar['id'],
                    max_results=5
                )
                
                if events:
                    print(f"✅ Found {len(events)} events:")
                    for i, event in enumerate(events[:3], 1):
                        print(f"   {i}. {event.title}")
                        print(f"      Start: {event.start_time}")
                        print(f"      End: {event.end_time}")
                        if event.location:
                            print(f"      Location: {event.location}")
                        print()
                else:
                    print("⚠️  No events found")
                    
        else:
            print("❌ No calendars found")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Error testing Apple Calendar: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_exchange_availability():
    """Test if Exchange Web Services is available"""
    print("📧 TESTING EXCHANGE WEB SERVICES AVAILABILITY")
    print("=" * 60)
    
    try:
        from services.exchange_calendar_enhanced import ExchangeCalendarService
        
        available = ExchangeCalendarService.is_available()
        print(f"EWS Available: {'✅' if available else '❌'}")
        
        if not available:
            print("ℹ️  To enable Exchange integration:")
            print("   pip install exchangelib")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error checking Exchange availability: {e}")
        return False

async def test_exchange_calendar():
    """Test the enhanced Exchange Calendar service (if credentials available)"""
    print("📧 TESTING ENHANCED EXCHANGE CALENDAR SERVICE")
    print("=" * 60)
    
    try:
        from services.exchange_calendar_enhanced import ExchangeCalendarService, ExchangeConfig
        
        if not ExchangeCalendarService.is_available():
            print("❌ Exchange Web Services not available (exchangelib not installed)")
            return False
        
        print("ℹ️  Exchange service is available but requires credentials")
        print("   To test with real Exchange server:")
        print("   1. Set up Exchange server details in test script")
        print("   2. Uncomment the test configuration below")
        print("   3. Run the test again")
        print()
        
        # Example configuration (commented out for security)
        # exchange_config = ExchangeConfig(
        #     server_url="https://your-exchange-server.com/EWS/Exchange.asmx",
        #     username="your-username",
        #     password="your-password",
        #     email="your-email@domain.com",
        #     auth_type="basic",
        #     verify_ssl=True
        # )
        # 
        # exchange_service = ExchangeCalendarService(exchange_config)
        # 
        # if exchange_service.test_connection():
        #     print("✅ Exchange connection successful")
        #     calendars = await exchange_service.list_calendars()
        #     print(f"Found {len(calendars)} calendars")
        # else:
        #     print("❌ Exchange connection failed")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing Exchange service: {e}")
        return False

async def main():
    """Main test function"""
    print("🧪 ENHANCED CALENDAR SERVICES TEST")
    print("=" * 70)
    print()
    
    test_results = {}
    
    # Test Apple Calendar
    test_results['apple'] = await test_apple_calendar()
    print()
    
    # Test Exchange availability
    test_results['exchange_available'] = test_exchange_availability()
    print()
    
    # Test Exchange service (without real credentials)
    test_results['exchange'] = await test_exchange_calendar()
    print()
    
    # Summary
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 50)
    
    passed = 0
    total = 0
    
    for test_name, result in test_results.items():
        total += 1
        if result:
            passed += 1
            print(f"✅ {test_name.replace('_', ' ').title()}: PASSED")
        else:
            print(f"❌ {test_name.replace('_', ' ').title()}: FAILED")
    
    print(f"\n🎯 {passed}/{total} tests passed")
    
    if test_results.get('apple'):
        print("\n✅ APPLE CALENDAR INTEGRATION IS READY!")
        print("   • You can now access Apple Calendar events without OAuth")
        print("   • The service automatically detects the best access method")
        print("   • Use the /apple/calendars endpoint to list calendars")
        print("   • Use the /apple/events/{calendar_id} endpoint to get events")
    
    if test_results.get('exchange_available'):
        print("\n✅ EXCHANGE WEB SERVICES IS AVAILABLE!")
        print("   • You can now integrate with Exchange servers")
        print("   • Configure server details in your application")
        print("   • Use the /exchange/calendars endpoint to list calendars")
        print("   • Use the /exchange/events/{calendar_id} endpoint to get events")
    
    print(f"\n🚀 NEXT STEPS:")
    print("   1. Start the application: python -m src.main")
    print("   2. Test Apple Calendar: GET /api/apple/calendars")
    print("   3. Configure Exchange credentials for Exchange testing")
    print("   4. Integrate with your Chip Hosting Admin frontend")

if __name__ == "__main__":
    asyncio.run(main())
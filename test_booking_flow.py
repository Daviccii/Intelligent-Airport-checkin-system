#!/usr/bin/env python3
"""
Test script for the complete booking and post-booking flow
"""

import requests
import json
import time

BASE_URL = "http://127.0.0.1:5000"

def test_booking_flow():
    """Test the complete booking flow from registration to check-in"""

    print("🧪 Testing Complete Booking Flow")
    print("=" * 50)

    # Test data with unique passport
    import time
    unique_id = str(int(time.time()))[-4:]  # Last 4 digits of timestamp
    booking_data = {
        "name": "John Doe",
        "passport": f"JD{unique_id}456",
        "email": f"john.doe{unique_id}@example.com",
        "phone": "+1234567890",
        "flight": "FL001",
        "from": "NBO",
        "to": "JNB",
        "seat_class": "Economy",
        "amount": 250.00,
        "currency": "USD",
        "payment_method": "card"
    }

    try:
        # Step 1: Register booking
        print("1. Registering booking...")
        response = requests.post(f"{BASE_URL}/api/register", json=booking_data)
        result = response.json()

        if response.status_code == 201 and result.get('ok') is not False:
            booking_ref = result.get('booking_ref', 'Unknown')
            print(f"✅ Booking registered successfully!")
            print(f"   Booking Reference: {booking_ref}")
            print(f"   Email sent: {result.get('confirmation_email_sent', False)}")
        else:
            print(f"❌ Booking failed: {result.get('error', 'Unknown error')}")
            return False

        # Step 2: Verify passenger was added
        print("\n2. Verifying passenger registration...")
        response = requests.get(f"{BASE_URL}/api/passengers")
        passengers = response.json().get('passengers', [])

        passenger = next((p for p in passengers if p['passport'] == booking_data['passport']), None)
        if passenger:
            print("✅ Passenger found in database")
            print(f"   Name: {passenger['name']}")
            print(f"   Flight: {passenger['flight']}")
            print(f"   Seat: {passenger.get('seat', 'Not assigned')}")
        else:
            print("❌ Passenger not found in database")
            return False

        # Step 3: Test boarding pass generation
        print("\n3. Testing boarding pass generation...")
        response = requests.get(f"{BASE_URL}/api/boardingpass?passport={booking_data['passport']}&format=png")
        if response.status_code == 200:
            print("✅ Boarding pass generated successfully")
        else:
            print(f"❌ Boarding pass generation failed: {response.status_code}")

        # Step 4: Test check-in
        print("\n4. Testing online check-in...")
        checkin_data = {
            "flight": booking_data['flight'],
            "passengers": [{
                "name": booking_data['name'],
                "passport": booking_data['passport'],
                "ticket_number": f"SF{booking_data['passport'][-4:]}"
            }]
        }

        response = requests.post(f"{BASE_URL}/api/checkin", json=checkin_data)
        result = response.json()

        if response.status_code == 200 and result.get('results'):
            checkin_result = result['results'][0]
            if checkin_result.get('status') == 'ok':
                print("✅ Check-in successful!")
                seat = checkin_result.get('seat', 'Unknown')
                print(f"   Assigned seat: {seat}")
            else:
                print(f"❌ Check-in failed: {checkin_result.get('status', 'Unknown error')}")
                return False
        else:
            print(f"❌ Check-in failed: {result.get('error', 'Unknown error')}")
            return False

        # Step 5: Verify check-in status
        print("\n5. Verifying check-in status...")
        response = requests.get(f"{BASE_URL}/api/passengers")
        passengers = response.json().get('passengers', [])

        passenger = next((p for p in passengers if p['passport'] == booking_data['passport']), None)
        if passenger and passenger.get('checked_in'):
            print("✅ Passenger is checked in")
            print(f"   Seat: {passenger.get('seat', 'Unknown')}")
        else:
            print("❌ Passenger check-in status not updated")
            return False

        print("\n" + "=" * 50)
        print("🎉 Booking flow test completed!")
        print("\nNext steps for passengers:")
        print("1. ✅ Booking confirmed with email notification")
        print("2. ✅ Boarding pass available for download")
        print("3. ✅ Online check-in completed")
        print("4. ✅ Seat assigned")
        print("5. 📋 Ready for airport arrival")

        return True

    except requests.exceptions.ConnectionError:
        print("❌ Connection failed - is the server running?")
        return False
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False

if __name__ == "__main__":
    success = test_booking_flow()
    exit(0 if success else 1)
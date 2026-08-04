"""
Test the dynamic API endpoints
"""

import requests
import json
from datetime import datetime, timedelta, timezone

# Test the dynamic flight search endpoint
def test_dynamic_flight_search():
    print("Testing dynamic flight search endpoint...")
    
    url = 'http://127.0.0.1:5000/api/dynamic/flights/search'
    
    test_cases = [
        {
            'origin': 'NBO',
            'destination': 'MBA',
            'departure_date': '2026-07-26',
            'passengers': 1,
            'seat_class': 'Economy'
        },
        {
            'origin': 'NBO',
            'destination': 'LHR',
            'departure_date': '2026-07-26',
            'passengers': 1,
            'seat_class': 'Economy'
        },
        {
            'origin': 'JFK',
            'destination': 'LAX',
            'departure_date': '2026-07-26',
            'passengers': 1,
            'seat_class': 'Economy'
        }
    ]
    
    for test_case in test_cases:
        print(f"\nTesting {test_case['origin']} -> {test_case['destination']}...")
        
        try:
            response = requests.post(url, json=test_case, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                print(f"  Status: OK")
                print(f"  Flights found: {data.get('count', 0)}")
                
                if data.get('flights'):
                    first_flight = data['flights'][0]
                    print(f"  Sample flight: {first_flight['flight_number']} - {first_flight['airline']}")
                    print(f"  Price: KES {first_flight['dynamic_pricing']['final_price']}")
                else:
                    print("  No flights returned")
            else:
                print(f"  Status: {response.status_code}")
                print(f"  Error: {response.text}")
                
        except requests.exceptions.ConnectionError:
            print("  Error: Could not connect to server. Make sure Flask app is running.")
        except Exception as e:
            print(f"  Error: {str(e)}")

if __name__ == '__main__':
    test_dynamic_flight_search()
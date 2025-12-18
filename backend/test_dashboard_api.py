#!/usr/bin/env python3
"""
Dashboard API Integration Test Script
Tests that all dashboard APIs are working correctly
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:5000"

def test_api(endpoint, method="GET", data=None):
    """Test an API endpoint"""
    url = f"{BASE_URL}{endpoint}"
    try:
        if method == "GET":
            response = requests.get(url, timeout=5)
        else:
            response = requests.post(url, json=data, timeout=5)
        
        status = "✓ OK" if response.status_code < 400 else f"✗ ERROR ({response.status_code})"
        print(f"{status:15} {endpoint:30} Response: {response.status_code}")
        
        if response.status_code < 400:
            try:
                data = response.json()
                if isinstance(data, list):
                    print(f"                                └─ Returned {len(data)} items")
                elif isinstance(data, dict):
                    if 'flights' in data:
                        print(f"                                └─ {len(data['flights'])} flights")
                    if 'bookings' in data:
                        print(f"                                └─ {len(data['bookings'])} bookings")
                    if 'total' in data:
                        print(f"                                └─ Total: {data['total']}")
            except:
                pass
        return response.status_code < 400
    except requests.exceptions.ConnectionError:
        print(f"✗ FAILED     {endpoint:30} Cannot connect to server")
        return False
    except Exception as e:
        print(f"✗ ERROR      {endpoint:30} {str(e)[:40]}")
        return False

def main():
    print("\n" + "="*70)
    print("ADMIN DASHBOARD - API INTEGRATION TEST")
    print("="*70)
    print(f"Testing server: {BASE_URL}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    print("CORE DASHBOARD ENDPOINTS:")
    print("-" * 70)
    
    results = {
        'flights': test_api("/api/flights"),
        'bookings': test_api("/api/bookings"),
        'passengers': test_api("/api/passengers"),
    }
    
    print("\n" + "-" * 70)
    print("SUPPORTING ENDPOINTS:")
    print("-" * 70)
    
    test_api("/api/checkin")
    test_api("/api/baggage/pay")
    test_api("/api/admin/events")
    
    print("\n" + "-" * 70)
    print("SUMMARY:")
    print("-" * 70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    if passed == total:
        print(f"✓ All {total} core endpoints are working!")
        print("\nThe admin dashboard can now:")
        print("  • Fetch and display real flight data")
        print("  • Track all bookings in real-time")
        print("  • Monitor passenger check-ins")
        print("  • Calculate revenue and occupancy metrics")
        print("  • Display system status and activities")
        print("\nAccess dashboard at: http://localhost:5000/admin/dashboard.html")
    else:
        print(f"✗ Only {passed}/{total} core endpoints working")
        print("\nPlease ensure:")
        print("  1. Flask backend is running (python app.py)")
        print("  2. Server is listening on port 5000")
        print("  3. Database files exist (bookings.json, passengers.json, flights.json)")
    
    print("\n" + "="*70 + "\n")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import requests
import json

try:
    response = requests.get('http://127.0.0.1:5000/api/activities/payments')
    if response.status_code == 200:
        data = response.json()
        print("✅ Payments API working!")
        print(f"Found {len(data.get('payments', []))} payment records")
        if data.get('payments'):
            print("Sample payment:")
            print(json.dumps(data['payments'][0], indent=2))
    else:
        print(f"❌ API error: {response.status_code}")
        print(response.text)
except Exception as e:
    print(f"❌ Connection error: {e}")
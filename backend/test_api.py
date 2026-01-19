import requests
import json

print('Testing payments API...')
try:
    response = requests.get('http://127.0.0.1:5000/api/activities/payments')
    print(f'API status: {response.status_code}')
    if response.status_code == 200:
        data = response.json()
        print(f'✅ Found {len(data.get("payments", []))} payment records')
        if data.get('payments'):
            print('✅ Payments data available')
        else:
            print('❌ No payments data in response')
    else:
        print(f'❌ API failed: {response.status_code}')
        print('Response:', response.text[:200])
except Exception as e:
    print(f'❌ Error: {e}')
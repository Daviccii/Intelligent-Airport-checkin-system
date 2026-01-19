import requests

try:
    response = requests.get('http://127.0.0.1:5000/api/activities/payments', timeout=5)
    print(f'Status: {response.status_code}')
    if response.status_code == 200:
        data = response.json()
        print(f'Payments: {len(data.get("payments", []))} records')
        if data.get('payments'):
            print('✅ API is working!')
        else:
            print('❌ No payment data')
    else:
        print(f'❌ Error: {response.text[:100]}')
except Exception as e:
    print(f'❌ Connection error: {e}')